# coding: utf-8
"""
This is a PyTorch implementation of the method for state representation learning described in the paper "Learning State
Representations with Robotic Priors" (Jonschkowski & Brock, 2015).

This program is based on the original implementation by Rico Jonschkowski (rico.jonschkowski@tu-berlin.de):
https://github.com/tu-rbo/learning-state-representations-with-robotic-priors

Example to run this program:
 python main.py --path slot_car_task_train.npz


TODO: generator to load images on the fly
"""
from __future__ import print_function, division

import argparse
import time

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import seaborn as sns
import numpy as np
import torch as th
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as models
from torch.autograd import Variable

# Init seaborn
sns.set()

# Python 2/3 compatibility
try:
    input = raw_input
except NameError:
    pass

try:
    from functools import reduce
except ImportError:
    pass

EPOCH_FLAG = 1  # Plot every EPOCH_FLAG epoch
BATCH_SIZE = 256  #  use 8 for ResNet in smaller gpu memories
NOISE_STD = 1e-6  # To avoid NaN (states must be different)
MAX_BACTHSIZE_GPU = 512  # For plotting, max batch_size before having memory issues


def observationsGenerator(observations, batch_size=64, cuda=False):
    """
    :param observations: (torch tensor)
    :param  batch_size: (int)
    :param cuda: (bool)
    """
    n_minibatches = len(observations) // batch_size + 1
    for i in range(n_minibatches):
        start_idx, end_idx = batch_size * i, batch_size * (i + 1)
        obs_var = Variable(observations[start_idx:end_idx], volatile=True)
        if cuda:
            obs_var = obs_var.cuda()
        yield obs_var


class SRLConvolutionalNetwork(nn.Module):
    """
    Convolutional Neural Net for State Representation Learning (SRL)
    input shape : 3-channel RGB images of shape (3 x H x W), where H and W are expected to be at least 224
    :param state_dim: (int)
    :param batch_size: (int)
    :param cuda: (bool)
    """

    def __init__(self, state_dim=2, batch_size=256, cuda=False):
        super(SRLConvolutionalNetwork, self).__init__()
        self.resnet = models.resnet18(pretrained=True)
        self.squeezeNet = models.squeezenet1_0(pretrained=True)
        # Freeze params
        for param in self.resnet.parameters():
            param.requires_grad = False
        # Replace the last fully-connected layer
        n_units = self.resnet.fc.in_features
        print("{} units in the last layer".format(n_units))
        self.resnet.fc = nn.Linear(n_units, state_dim)
        if cuda:
            self.resnet.cuda()
        self.noise = GaussianNoise(batch_size, state_dim, NOISE_STD, cuda=cuda)

    def forward(self, x):
        x = self.resnet(x)
        x = self.noise(x)
        return x


class SRLDenseNetwork(nn.Module):
    """
    Feedforward Neural Net for State Representation Learning (SRL)
    input shape : 3-channel RGB images of shape (3 x H x W) (to be consistent with CNN network)
    :param input_dim: (int) 3 x H x H
    :param state_dim: (int)
    :param batch_size: (int)
    :param cuda: (bool)
    :param n_hidden: (int)
    """

    def __init__(self, input_dim, state_dim=2,
                 batch_size=256, cuda=False, n_hidden=32):
        super(SRLDenseNetwork, self).__init__()
        self.fc1 = nn.Linear(input_dim, n_hidden)
        self.fc2 = nn.Linear(n_hidden, state_dim)
        self.noise = GaussianNoise(batch_size, state_dim, NOISE_STD, cuda=cuda)

    def forward(self, x):
        # Flatten input
        x = x.view(x.size(0), -1)
        x = F.relu(self.fc1(x))
        x = self.fc2(x)
        x = self.noise(x)
        return x

class GaussianNoise(nn.Module):
    """
    Gaussian Noise layer
    :param batch_size: (int)
    :param input_dim: (int)
    :param std: (float) standard deviation
    :param mean: (float)
    :param cuda: (bool)
    """

    def __init__(self, batch_size, input_dim, std, mean=0, cuda=False):
        super(GaussianNoise, self).__init__()
        self.std = std
        self.mean = mean
        self.noise = Variable(th.zeros(batch_size, input_dim))
        if cuda:
            self.noise = self.noise.cuda()

    def forward(self, x):
        if self.training:
            self.noise.data.normal_(self.mean, std=self.std)
            return x + self.noise
        return x


class RoboticPriorsLoss(nn.Module):
    def __init__(self, model, l1_reg=0):
        super(RoboticPriorsLoss, self).__init__()
        # Retrieve only trainable and regularizable parameters (we should exclude biases)
        self.reg_params = [param for name, param in model.named_parameters() if
                           ".bias" not in name and param.requires_grad]
        n_params = sum([reduce(lambda x, y: x * y, param.size()) for param in self.reg_params])
        self.l1_coeff = (l1_reg / n_params)

    def forward(self, states, next_states, dissimilar_pairs, same_actions_pairs):
        """
        :param states: (th Variable)
        :param next_states: (th Variable)
        :param dissimilar_pairs: (th tensor)
        :param same_actions_pairs: (th tensor)
        :return: (th Variable)
        """
        state_diff = next_states - states
        state_diff_norm = state_diff.norm(2, dim=1)
        similarity = lambda x, y: th.exp(-(x - y).norm(2, dim=1) ** 2)
        # try:
        temp_coherence_loss = (state_diff_norm ** 2).mean()
        causality_loss = similarity(states[dissimilar_pairs[:, 0]],
                                states[dissimilar_pairs[:, 1]]).mean()
        proportionality_loss = ((state_diff_norm[same_actions_pairs[:, 0]] -
                                 state_diff_norm[same_actions_pairs[:, 1]]) ** 2).mean()

        repeatability_loss = (
            similarity(states[same_actions_pairs[:, 0]], states[same_actions_pairs[:, 1]]) *
            (state_diff[same_actions_pairs[:, 0]] - state_diff[same_actions_pairs[:, 1]]).norm(2, dim=1) ** 2).mean()

        l1_loss = sum([th.sum(th.abs(param)) for param in self.reg_params])

        loss = 1 * temp_coherence_loss + 1 * causality_loss + 5 * proportionality_loss + 5 * repeatability_loss + self.l1_coeff * l1_loss
        return loss

class SRL4robotics:
    """
    :param state_dim: (int)
    :param model_type: (str) one of "cnn" or "mlp"
    :param seed: (int)
    :param learning_rate: (float)
    :param l1_reg: (float)
    :param cuda: (bool)
    """

    def __init__(self, state_dim, model_type="cnn",
                 seed=1, learning_rate=0.001, l1_reg=0.0, cuda=False):

        self.state_dim = state_dim
        self.batch_size = BATCH_SIZE
        self.cuda = cuda

        np.random.seed(seed)
        th.manual_seed(seed)
        if cuda:
            th.cuda.manual_seed(seed)

        if model_type == "cnn":
            self.model = SRLConvolutionalNetwork(self.state_dim, self.batch_size, cuda)
        elif model_type == "mlp":
            input_dim = 224 * 224 * 3
            self.model = SRLDenseNetwork(input_dim, self.state_dim, self.batch_size, cuda)
        else:
            raise ValueError("Unknown model: {}".format(model_type))
        print("Using {} model".format(model_type))

        if cuda:
            self.model.cuda()
        learnable_params = [param for param in self.model.parameters() if param.requires_grad]
        self.optimizer = th.optim.Adam(learnable_params, lr=learning_rate)
        self.l1_reg = l1_reg

    def _predFn(self, observations, restore_train=True):
        # test mode
        self.model.eval()
        states = self.model(observations)
        if restore_train:
            self.model.train()
        if self.cuda:
            return states.data.cpu().numpy()
        return states.data.numpy()

    def _batchPredStates(self, observations):
        predictions = []
        for obs_var in observationsGenerator(th.from_numpy(observations), MAX_BACTHSIZE_GPU, cuda=self.cuda):
            predictions.append(self._predFn(obs_var))
        return np.concatenate(predictions, axis=0)

    def learn(self, observations, actions, rewards, episode_starts):

        # PREPARE DATA -------------------------------------------------------------------------------------------------
        # here, we normalize the observations, organize the data into minibatches
        # and find pairs for the respective loss terms

        # We assume that observations are already preprocessed
        observations = observations.astype(np.float32)

        num_samples = observations.shape[0] - 1  # number of samples

        # indices for all time steps where the episode continues
        indices = np.array([i for i in range(num_samples) if not episode_starts[i + 1]], dtype='int64')
        np.random.shuffle(indices)

        # split indices into minibatches
        minibatchlist = [np.array(sorted(indices[start_idx:start_idx + self.batch_size]))
                         for start_idx in range(0, num_samples - self.batch_size + 1, self.batch_size)]
        if len(minibatchlist[-1]) < self.batch_size:
            print("Removing last minibatch of size {} < batch_size".format(len(minibatchlist[-1])))
            del minibatchlist[-1]

        find_same_actions = lambda index, minibatch: \
            np.where(np.prod(actions[minibatch] == actions[minibatch[index]], axis=1))[0]
        same_actions = [
            np.array([[i, j] for i in range(self.batch_size) for j in find_same_actions(i, minibatch) if j > i],
                     dtype='int64') for minibatch in minibatchlist]

        # check with samples should be dissimilar because they lead to different rewards aften the same actions
        find_dissimilar = lambda index, minibatch: \
            np.where(np.prod(actions[minibatch] == actions[minibatch[index]], axis=1) *
                     (rewards[minibatch + 1] != rewards[minibatch[index] + 1]))[0]
        dissimilar = [np.array([[i, j] for i in range(self.batch_size) for j in find_dissimilar(i, minibatch) if j > i],
                               dtype='int64') for minibatch in minibatchlist]

        for item in same_actions + dissimilar:
            if len(item) == 0:
                msg = "No similar or dissimilar pair found for at least one minibatch\n"
                msg += "=> Consider increasing the batch_size or changing the seed"
                raise ValueError(msg)

        # TRAINING -----------------------------------------------------------------------------------------------------
        criterion = RoboticPriorsLoss(self.model, self.l1_reg)

        self.model.train()
        start_time = time.time()
        for epoch in range(N_EPOCHS):
            # In each epoch, we do a full pass over the training data:
            epoch_loss, epoch_batches = 0, 0
            enumerated_minibatches = list(enumerate(minibatchlist))
            np.random.shuffle(enumerated_minibatches)
            for i, batch in enumerated_minibatches:
                diss = dissimilar[i][np.random.permutation(dissimilar[i].shape[0])]
                same = same_actions[i][np.random.permutation(same_actions[i].shape[0])]  # [:MAX_PAIR_PER_SAMPLE * self.batch_size]
                diss, same = th.from_numpy(diss), th.from_numpy(same)
                obs = Variable(th.from_numpy(observations[batch]))
                next_obs = Variable(th.from_numpy(observations[batch + 1]))
                if self.cuda:
                    obs, next_obs = obs.cuda(), next_obs.cuda()
                    same, diss = same.cuda(), diss.cuda()

                states, next_states = self.model(obs), self.model(next_obs)
                self.optimizer.zero_grad()
                loss = criterion(states, next_states, diss, same)
                loss.backward()
                self.optimizer.step()
                epoch_loss += loss.data[0]
                epoch_batches += 1

            # Then we print the results for this epoch:
            if (epoch + 1) % EPOCH_FLAG == 0:
                print("Epoch {:3}/{}, loss:{:.4f}".format(epoch + 1, N_EPOCHS, epoch_loss / epoch_batches))
                print("{:.2f}s/epoch".format((time.time() - start_time) / (epoch + 1)))

                # Optionally plot the current state space
                plot_representation(self._batchPredStates(observations), rewards, add_colorbar=epoch == 0,
                                    name="Learned State Representation (Training Data)")

        plt.close("Learned State Representation (Training Data)")

        # return predicted states for training observations
        return self._batchPredStates(observations)

    def predStates(self, observations):
        observations = observations.astype(np.float32)
        obs_var = Variable(th.from_numpy(observations), volatile=True)
        if self.cuda:
            obs_var = obs_var.cuda()
        states = self._predFn(obs_var, restore_train=False)
        return states


def saveImagesAndReprToTxt(state_representations, log_folder):
    raise NotImplementedError("states to txt not finished yet")
    header = ['image_path', 'state']
    print("state_representations: {}".format(state_representations))
    # for image_path, state_array in zip(img_paths, state_representations):
    img_paths = np.array()  # TODO: load()
    images2states = {'image_path': img_paths, 'state': state_representations}

    # data is a dict here  (if not, use *data)
    # representations_df = pd.read_csv(, usecols=['image_path','state'])
    np.savez('{}/Images2States.npz', **data)
    representations_df.sort_values(by='image_path', inplace=True)

    print("Latest scores logged so far: \n".format(representations_df.tail(5)))
    representations_df.to_csv("{}/imagePathsAndLearnedRepresentations.txt", header=header)
    print('saved pairs of img-path and their learned representation  to file ')
    print('Saved npz file {}'.format(np.load(my_npz_file)))


def plot_3d_representation(states, rewards, name="Learned State Representation", add_colorbar=True):
    plt.ion()
    fig = plt.figure(name)
    plt.clf()
    ax = fig.add_subplot(111, projection='3d')
    im = ax.scatter(states[:, 0], states[:, 1], states[:, 2],
                    s=7, c=np.clip(rewards, -1, 1), cmap='coolwarm', linewidths=0.1)
    ax.set_xlabel('State dimension 1')
    ax.set_ylabel('State dimension 2')
    ax.set_zlabel('State dimension 3')
    if add_colorbar:
        fig.colorbar(im, label='Reward')
    plt.draw()
    plt.pause(0.0001)


def plot_representation(states, rewards, name="Learned State Representation", add_colorbar=True):
    state_dim = states.shape[1]
    if state_dim == 2:
        plot_2d_representation(states, rewards, name, add_colorbar)
    elif state_dim == 3:
        plot_3d_representation(states, rewards, name, add_colorbar)
    else:
        # TODO: 1d plot + PCA for more dimensions
        print("[WARNING] state dim = {} is not supported for plotting".format(state_dim))


def plot_2d_representation(states, rewards, name="Learned State Representation", add_colorbar=True):
    plt.ion()
    plt.figure(name)
    plt.clf()
    plt.scatter(states[:, 0], states[:, 1], s=7, c=np.clip(rewards, -1, 1), cmap='coolwarm', linewidths=0.1)
    plt.xlabel('State dimension 1')
    plt.ylabel('State dimension 2')
    if add_colorbar:
        plt.colorbar(label='Reward')
    plt.pause(0.0001)


def plot_observations(observations, name='Observation Samples'):
    plt.ion()
    plt.figure(name)
    m, n = 8, 10
    for i in range(m * n):
        plt.subplot(m, n, i + 1)
        plt.imshow(observations[i].reshape(16, 16, 3), interpolation='nearest')
        plt.gca().invert_yaxis()
        plt.xticks([])
        plt.yticks([])
    plt.pause(0.0001)

def set_cuda(use_cuda):
    if use_cuda:
        # To tackle GPU memory issues, th.cuda.set_default_device(1) and set_device() are both discouraged, use instead A) MLP network, SqueezeNet instead of ResNet or B)
        # See how second gpu memory is less used, therefore we can set it (recommended as setDevice is discouraged): CUDA_VISIBLE_DEVICES=1 python main.py (to set the second gpu memory for use)
        # A future enhancement TODO for running on multiple GPU: CUDA_VISIBLE_DEVICES=2,3 python main.py   and then also model = torch.nn.DataParallel(model, device_ids=[0,1]).cuda()
        device = th.cuda.current_device()+1
        print ("Current device is the {}{}. setDevice is discouraged, run instead: CUDA_VISIBLE_DEVICES=1 python main.py (to set the second gpu memory)".format(device,'nd' if device==2 else 'st'))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='PyTorch SRL with robotic priors')
    parser.add_argument('--epochs', type=int, default=50, metavar='N',
                        help='number of epochs to train (default: 50)')
    parser.add_argument('--seed', type=int, default=1, metavar='S',
                        help='random seed (default: 1)')
    parser.add_argument('--state_dim', type=int, default=2, help='state dimension (default: 2)')
    parser.add_argument('-bs', '--batch_size', type=int, default=256, help='batch_size (default: 256)')
    parser.add_argument('-lr', '--learning_rate', type=float, default=0.005, help='learning rate (default: 0.005)')
    parser.add_argument('--l1', type=float, default=0.0, help='L1 regularization coeff (default: 0.0)')
    parser.add_argument('--no-cuda', action='store_true', default=False, help='disables CUDA training')
    parser.add_argument('--model_type', type=str, default="cnn", help='Model architecture (default: "cnn")')
    parser.add_argument('--path', type=str, default="", help='Path to npz file')
    parser.add_argument('--experiment_path', type=str, default='logs/default',
                        help='Folder within logs/ where the experiment model and KNN images and plots will be saved')

    args = parser.parse_args()
    args.cuda = not args.no_cuda and th.cuda.is_available()
    N_EPOCHS = args.epochs
    BATCH_SIZE = args.batch_size
    EXPERIMENT_PATH = args.experiment_path

    print('\nDataset npz file: {}\n'.format(args.path))
    print('Expriment path: {}'.format(args.experiment_path))

    print('Loading data ... ')
    training_data = np.load(args.path)
    observations, actions = training_data['observations'], training_data['actions']
    rewards, episode_starts = training_data['rewards'], training_data['episode_starts']

    # Demo with rico's original data
    if len(observations.shape) == 2:
        import cv2
        from preprocessing.preprocess import IMAGE_WIDTH, IMAGE_HEIGHT
        from preprocessing.utils import preprocessInput

        observations = observations.reshape(-1, 16, 16, 3) * 255.
        obs = np.zeros((observations.shape[0], IMAGE_WIDTH, IMAGE_HEIGHT, 3))
        for i in range(len(observations)):
            obs[i] = cv2.resize(observations[i], (IMAGE_WIDTH, IMAGE_HEIGHT))
        del observations
        observations = preprocessInput(obs, mode="image_net")

    # (batch_size, width, height, n_channels) -> (batch_size, n_channels, height, width)
    observations = np.transpose(observations, (0, 3, 2, 1))
    print("Observations shape: {}".format(observations.shape))

    print('Learning a state representation ... ')
    srl = SRL4robotics(args.state_dim, args.model_type, args.seed,
                       learning_rate=args.learning_rate, l1_reg=args.l1, cuda=args.cuda)
    learned_states = srl.learn(observations, actions, rewards, episode_starts)
    # saveImagesAndReprToTxt(learned_states, EXPERIMENT_PATH)
    plot_representation(learned_states, rewards, name='Training Data', add_colorbar=True)

    input('\nPress any key to exit.')
