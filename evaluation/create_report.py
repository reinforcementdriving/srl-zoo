from __future__ import print_function, division, absolute_import

import argparse
import json
import os

import pandas as pd


def getKnnMse(path):
    """
    Retrieve knn mse score
    :param path: (str)
    :return: (float)
    """
    try:
        with open(path) as f:
            return json.load(f)['knn_mse']
    except IOError:
        print("knn_mse.json not found for {}".format(path))
        return -1


parser = argparse.ArgumentParser(description='Create a report file for a given dataset')
parser.add_argument('-d', '--data_log_folder', type=str, default="", required=True, help='Path to a dataset log folder')
args = parser.parse_args()

assert os.path.isdir(args.data_log_folder), "--data_log_folder must be a path to a valid folder"

dataset_logfolder = args.data_log_folder
experiments = []
for item in os.listdir(dataset_logfolder):
    if 'baselines' not in item and os.path.isdir('{}/{}'.format(dataset_logfolder, item)):
        experiments.append(item)
experiments.sort()
print("Found {} experiments".format(len(experiments)))

knn_mse = []
# Add here keys from exp_config.json that should be saved in the csv report file
exp_configs = {'model_type': [], 'state_dim': [], 'epochs': [], 'batch_size': []}

for experiment in experiments:

    with open('{}/{}/exp_config.json'.format(dataset_logfolder, experiment)) as f:
        exp_config = json.load(f)
    for key in exp_configs.keys():
        exp_configs[key].append(exp_config.get(key, None))

    knn_mse.append(getKnnMse('{}/{}/knn_mse.json'.format(dataset_logfolder, experiment)))

# Baselines
for baseline in os.listdir(dataset_logfolder + "/baselines"):
    try:
        with open('{}/baselines/{}/exp_config.json'.format(dataset_logfolder, baseline)) as f:
            exp_config = json.load(f)
    except IOError:
        print("exp_config.json not found for {}".format(baseline))
        continue
    for key in exp_configs.keys():
        exp_configs[key].append(exp_config.get(key, None))

    knn_mse.append(getKnnMse('{}/baselines/{}/knn_mse.json'.format(dataset_logfolder, baseline)))
    experiments.append(baseline)

exp_configs.update({'experiments': experiments, 'knn_mse': knn_mse})

result_df = pd.DataFrame(exp_configs)
result_df.to_csv('{}/results.csv'.format(dataset_logfolder), sep=",", index=False)
print("Saved results to {}/results.csv".format(dataset_logfolder))
print("Last 10 experiments:")
print(result_df.tail(10))
