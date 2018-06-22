# State Representation Learning Zoo with PyTorch

A collection of state representation learning (SRL) methods for Reinforcement Learning, written using PyTorch.

Availables methods:

- SRL with Robotic Priors + extensions (stereovision, additional priors)
- Denoising Autoencoder (DAE)
- Variational Autoencoder (VAE) and beta-VAE
- PCA
- Supervised Learning
- Forward, Inverse Models
- Triplet Network (for stereovision only)

Related papers (robotic priors):
- "Learning State Representations with Robotic Priors" (Jonschkowski and Brock, 2015), paper: [http://tinyurl.com/gly9sma](http://tinyurl.com/gly9sma)
- "Unsupervised state representation learning with robotic priors: a robustness benchmark" (Lesort, Seurin et al., 2017), paper: [https://arxiv.org/pdf/1709.05185.pdf](https://arxiv.org/pdf/1709.05185.pdf)


Table of Contents
=================

  * [Config Files](#config-files)
    * [Base Config](#base-config)
    * [Dataset config](#dataset-config)
    * [Experiment Config](#experiment-config)
  * [Dataset Format](#dataset-format)
  * [Launch script](#launch-script)
  * [Pipeline Script](#pipeline-script)
    * [Examples](#examples)
  * [Learn a state representation](#learn-a-state-representation)
  * [Multiple Cameras](#multiple-cameras)
    * [Stacked Observations](#stacked-observations)
    * [Triplets of Observations](#triplets-of-observations)
  * [Evaluation and Plotting](#evaluation-and-plotting)
  * [Learned Space Visualization](#learned-space-visualization)
    * [Create a report](#create-a-report)
    * [Plot a Learned Representation](#plot-a-learned-representation)
    * [Interactive Plot](#interactive-plot)
    * [Create a KNN Plot and Compute KNN-MSE](#create-a-knn-plot-and-compute-knn-mse)
  * [Baselines](#baselines)
    * [Supervised Learning](#supervised-learning)
    * [Autoencoder](#autoencoder)
    * [VAE](#vae)
    * [Principal Components Analysis](#principal-components-analysis)
  * [SRL Server for Reinforcement Learning](#srl-server-for-reinforcement-learning)
  * [Running Tests](#running-tests)
  * [Installation: Dependencies](#installation-dependencies)
    * [Recommended Method: Use saved conda environment](#recommended-method-use-saved-conda-environment)
    * [Python 3](#python-3)
    * [Python 2](#python-2)
    * [Dependencies details](#dependencies-details)
  * [Example Data](#example-data)
* [Troubleshooting](#troubleshooting)
  * [CUDA out of memory error](#cuda-out-of-memory-error)


## Installation: Dependencies

Recommended configuration: Ubuntu 16.04 with python 2.7 or >= 3.5

### Recommended Method: Anaconda Environment

#### Python 3
Please use `environment.yml` file from [https://github.com/araffin/robotics-rl-srl](https://github.com/araffin/robotics-rl-srl)
To create a conda environment from this file:

```
conda env create -f environment.yml
```

#### Python 2

Create the new environment `srl` from `environment.yml` file:
```
conda env create -f environment.yml
```

Then activate it using:
```
source activate srl
```

Alternatively, you can use requirements.txt file:
```
pip install -r requirements.txt
```
In that case, you will need to install OpenCV too (cf below).

#### Dependencies details

- OpenCV (version >= 2.4)
```
conda install -c menpo opencv
```
or
```
sudo apt-get install python-opencv (opencv 2.4 - python2)
```

- PyTorch
- PyTorchVision
- Numpy
- Scikit-learn
- Pandas

For plotting:
- matplotlib
- seaborn
- Pillow

For display enhancement:
- termcolor
- tqdm


## Config Files

### Base Config
Config common to all dataset can found in [configs/default.json](configs/default.json).

### Dataset config
All dataset must be placed in the `data/` folder.
Each dataset must contain a `dataset_config.json` file, an example can be found [here](configs/example_dataset_config.json).
This config file describes specific variables to this dataset.


### Experiment Config
Experiment config file is generated by the `pipeline.py` script. An example can be found [here](configs/example_exp_config.json))

## Dataset Format

In order to use SRL methods on a dataset, this dataset must be preprocessed and formatted as in the [example dataset](https://drive.google.com/open?id=154qMJHgUnzk0J_Hxmr2jCnV1ipS7o1D5).
We recommend you downloading this example dataset to have a concrete and working example of what a preprocessed dataset looks like.

NOTE: If you use data generated with the [RL Repo](https://github.com/araffin/robotics-rl-srl), the dataset will be already preprocessed, so you don't need to bother about this step.

The dataset format is as followed:

0. You must provide a dataset config file (see previous section) that contains at least if the ground truth is the relative position or not
1. Images are grouped by episode in different folders (`record_{03d}/` folders)
2. At the root of the dataset folder, preprocessed_data.npz contains numpy arrays ('episode_starts', 'rewards', 'actions')
3. At the root of the dataset folder, ground_truth.npz contains numpy arrays ('target_positions', 'ground_truth_states', 'images_path')

The exact format for each numpy array can be found in the example dataset (or in the [RL Repo](https://github.com/araffin/robotics-rl-srl)).
Note: the variables 'arm_states' and 'button_positions' were renamed 'ground_truth_states' and 'target_positions'


## Launch script
Located [here](launch.sh), it is a shell script that launches multiple grid searches, trains the baselines and calls the report script.
You have to edit `$data_folder` and make sure of the parameters for knn evaluation before running it:
```
./launch.sh
```

## Pipeline Script
It learns state representations and evaluates them using knn-mse.

To generate data for Kuka and Mobile Robot environment, please see the RL repo: [https://github.com/araffin/robotics-rl-srl](https://github.com/araffin/robotics-rl-srl).

Baxter data used in the paper are not public yet. However you can generate new data using [Baxter Simulator](https://github.com/araffin/arm_scenario_simulator) and [Baxter Experiments](https://github.com/NataliaDiaz/arm_scenario_experiments)

```
python pipeline.py [-h] [-c EXP_CONFIG] [--data-folder DATA_FOLDER]
                   [--base_config BASE_CONFIG]
-c EXP_CONFIG, --exp-config EXP_CONFIG
                     Path to an experiment config file
--data-folder DATA_FOLDER
                     Path to a dataset folder
--base_config BASE_CONFIG
                     Path to overall config file, it contains variables
                     independent from datasets (default:
                     /configs/default.json)
```

### Examples

Grid search:
```
python pipeline.py --data-folder data/staticButtonSimplest/
```

Reproducing an experiment:
```
python pipeline.py -c path/to/exp_config.json
```


## Learn a State Representation

Usage:
```
python train.py [-h] [--epochs N] [--seed S] [--state-dim STATE_DIM]
                [-bs BATCH_SIZE] [--training-set-size TRAINING_SET_SIZE]
                [-lr LEARNING_RATE] [--l1-reg L1_REG] [--no-cuda] [--no-plots]
                [--model-type MODEL_TYPE] --data-folder DATA_FOLDER
                [--log-folder LOG_FOLDER]

  -h, --help            show this help message and exit
  --epochs N            number of epochs to train (default: 50)
  --seed S              random seed (default: 1)
  --state-dim STATE_DIM
                        state dimension (default: 2)
  -bs BATCH_SIZE, --batch-size BATCH_SIZE
                        batch_size (default: 256)
  --training-set-size TRAINING_SET_SIZE
                        Limit size of the training set (default: -1)
  -lr LEARNING_RATE, --learning-rate LEARNING_RATE
                        learning rate (default: 0.005)
  --l1-reg L1_REG       L1 regularization coeff (default: 0.0)
  --no-cuda             disables CUDA training
  --no-plots            disables plots
  --model-type MODEL_TYPE
                        Model architecture (default: "resnet")
  --data-folder DATA_FOLDER
                        Dataset folder
  --log-folder LOG_FOLDER
                        Folder within logs/ where the experiment model and
                        plots will be saved
  --multi-view          Enable use of multiple camera (two)
  --no-priors           Disable use of priors - in case of triplet loss

```


Example:
```
python train.py --data-folder data/path/to/dataset
```

In case of `--multi-view` enabled make sure you set the global variable N_CHANNELS in file `preprocess.py` to 6
if `--model-type` is custom_cnn ( 9 if `triplet_cnn`).


## Multiple Cameras

### Stacked Observations

Using the `custom_cnn` architecture, it is possible to pass pairs of images from different views stacked along the channels' dimension i.e of dim (224,224,6).

To use this functionality to perform state representation learning with priors, enable `--multi-view` (see usage of script train.py),
and set the global variable N_CHANNELS in file `preprocess.py` to 6.


### Triplets of Observations

Using the `triplet_cnn` architecture, it is possible to learn representation of states using a dataset of triplets, i.e tuples made of an anchor, a positive and a negative observation.

The anchor and the positive observation are views of the scene at the same time step, but from different cameras.

The negative example is an image from the same camera as the anchor but at a different time step selected randomly among images in the same record.

In our case the TCN-like architecture is made of a pre-trained ResNet with an extra fully connected layer (embedding).

To use this functionality also enable `--multi-view`, preferably `--no-priors` (see usage of script train.py),
and set the global variable N_CHANNELS in file `preprocess.py` to 9 for training (3 otherwise).

Related papers:
- "Time-Contrastive Networks: Self-Supervised Learning from Video" (P. Sermanet et al., 2017), paper: [https://arxiv.org/abs/1704.06888](https://arxiv.org/abs/1704.06888)

## Evaluation and Plotting

## Learned Space Visualization

To view the learned state and play with the latent space of a VAE, autoencoder or srl-priors, you may use:
```bash
python -m enjoy.enjoy_latent --log-dir logs/nameOfTheDataset/nameOfTheModel
```

### Create a report
After a report you can create a csv report file using:
```
python evaluation/create_report.py -d logs/nameOfTheDataset/
```

### Plot a Learned Representation
You can plot a learned representation with:
```
python plotting/representation_plot.py -i path/to/states_rewards.npz
```

You can also plot ground truth states with:
```
python plotting/representation_plot.py --data-folder path/to/datasetFolder/
```

To have a different color per episode, you have to pass `--data-folder` argument along with `--color-episode`.

### Interactive Plot

You can have an interactive plot of a learned representation using:
```
python plotting/interactive_plot.py --data-folder path/to/datasetFolder/ -i path/to/states_rewards.npz
```
When you click on a state in the representation plot (left click for 2D, **right click for 3D plots**!), it shows the corresponding image along with the reward and the coordinates in the space.

Pass `--multi-view` as argument to visualize in case of multiple cameras.

You can also plot ground truth states when you don't specify a npz file:
```
python plotting/interactive_plot.py --data-folder path/to/datasetFolder/
```

### Create a KNN Plot and Compute KNN-MSE

Usage:
```
python plotting/knn_images.py [-h] --log-folder LOG_FOLDER
                     [--seed SEED] [-k N_NEIGHBORS] [-n N_SAMPLES]

KNN plot and KNN MSE

--log-folder LOG_FOLDER
                      Path to a log folder
--seed SEED           random seed (default: 1)
-k N_NEIGHBORS, --n-neighbors N_NEIGHBORS
                      Number of nearest neighbors (default: 5)
-n N_SAMPLES, --n-samples N_SAMPLES
                      Number of test samples (default: 10)
--multi-view          To deal with multi view data format

```

Example:
```
python plotting/knn_images.py --log-folder path/to/an/experiment/log/folder
```

## Baselines

Baseline models are saved in `logs/nameOfTheDataset/baselines/` folder.

### Supervised Learning

Example:
```
python -m baselines.supervised --data-folder path/to/data/folder
```

### Autoencoder

Gaussian noise is added to the input with a factor `0.1`.

Example:
```
python -m baselines.autoencoder --data-folder path/to/data/folder --state-dim 3 --noise-factor 0.1
```

### VAE

Example:
```
python -m baselines.vae --data-folder path/to/data/folder --state-dim 3
```

You can also designate the beta weight for the KL divergence:
```
python -m baselines.vae --data-folder path/to/data/folder --state-dim 3 --beta 1.0
```

### Principal Components Analysis

PCA:
```
python -m baselines.pca --data-folder path/to/data/folder --state-dim 3
```

## SRL Server for Reinforcement Learning

This feature is currently experimental. It will launch a server that will learn a srl model and send a response to the RL client when  it is ready.
```
python server.py
```

## Running Tests

Download test dataset [here](https://drive.google.com/open?id=154qMJHgUnzk0J_Hxmr2jCnV1ipS7o1D5) and put it in `data/` folder.
```
./run_tests.sh
```

## Example Data
You can reproduce Rico Jonschkowski's results by downloading npz files from the original [github repository](https://github.com/tu-rbo/learning-state-representations-with-robotic-priors) and placing them in the `data/` folder.

It was tested with the following commit (checkout this one to be sure it will work): [https://github.com/araffin/srl-zoo/commit/5175b88a891c240f393b717dd1866435c73ebbda](https://github.com/araffin/srl-zoo/commit/5175b88a891c240f393b717dd1866435c73ebbda)

You have to do:
```
git checkout 5175b88a891c240f393b717dd1866435c73ebbda
```

Then run (for example):
```
python main.py --path data/slot_car_task_train.npz
```


## Troubleshooting

### CUDA out of memory error

1.  python train.py --data-folder data/staticButtonSimplest
```
RuntimeError: cuda runtime error (2) : out of memory at /b/wheel/pytorch-src/torch/lib/THC/generic/THCStorage.cu:66
```

SOLUTION 1: CUDA_VISIBLE_DEVICES – Masking GPUs

CUDA_VISIBLE_DEVICES=0 Only Device 0 will be visible
NOTE: Do not set a device id superior to the number of GPU you have, or it will run on your CPU and may freeze your display.


SOLUTION 2: Decrease the batch size, e.g. 32-64 in GPUs with little memory. Warning: computing the priors might not work

SOLUTION 3: Use simple 2-layers neural network model
python train.py --data-folder data/staticButtonSimplest --model-type mlp
