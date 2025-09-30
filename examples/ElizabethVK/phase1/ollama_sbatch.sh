#!/bin/bash -l

## This file is called `hello_sbatch.sh`
#SBATCH --time=00:05:00
#SBATCH --qos=default
#SBATCH --partition=gpu
#SBATCH --account=p200981                  # Put your project ID
#SBATCH --nodes=1                          # num of nodes
#SBATCH --ntasks=1                         # number of tasks
#SBATCH --ntasks-per-node=1                # number of tasks per node


echo "Date              = $(date)"
echo "Hostname          = $(hostname -s)"
echo "Working Directory = $(pwd)"


# Load the env
module add Apptainer


# Run the processing
apptainer pull docker://ollama/ollama
apptainer exec --nv ollama_latest.sif ollama serve
