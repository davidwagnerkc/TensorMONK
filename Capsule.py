""" tensorMONK's :: Capsule Network                                         """

from __future__ import print_function, division
import sys
import timeit
import os
import argparse
import numpy as np
import torch
import core
from core.NeuralEssentials import DataSets, MakeModel, VisPlots, SaveModel

# DistributedDataParallel 
import torch.utils.data
import torch.utils.data.distributed
from torch.nn.parallel import DistributedDataParallel
import torch.distributed as dist

#torch.multiprocessing.set_start_method('spawn')

def parse_args():
    parser = argparse.ArgumentParser(description="CapsuleNet")
    parser.add_argument("-A", "--Architecture", type=str, default="capsule")
    parser.add_argument("-B", "--BSZ", type=int, default=32)
    parser.add_argument("-E", "--Epochs", type=int, default=6)

    parser.add_argument("--optimizer", type=str, default="adam",
                        choices=["adam", "sgd"])
    parser.add_argument("--learningRate", type=float, default=0.06)

    parser.add_argument("--default_gpu", type=int,  default=0)
    parser.add_argument("--gpus", type=int, default=1)
    parser.add_argument("--cpus", type=int, default=6)

    parser.add_argument("-I", "--ignore_trained", action="store_true")
    parser.add_argument("--local_rank", default=0, type=int)

    return parser.parse_args()


def trainMONK():
    r"""An example to train 3 layer cnn on mnist and fashion mnist.
    """
    args = parse_args()
    args.distributed = True
    #if 'WORLD_SIZE' in os.environ:
    #    args.distributed = int(os.environ['WORLD_SIZE']) > 1

    if args.distributed:
        n_gpu = torch.cuda.device_count()
        assert args.BSZ > n_gpu and args.BSZ % n_gpu == 0
        torch.cuda.set_device(args.local_rank)
        torch.distributed.init_process_group(backend='nccl', init_method='env://')

    trData, vaData, teData, n_labels, tensor_size = \
        DataSets("fashionmnist", data_path="data", n_samples=args.BSZ)
    
    train_sampler = torch.utils.data.distributed.DistributedSampler(trData)
    trData = torch.utils.data.DataLoader(trData, sampler=train_sampler, batch_size=args.BSZ, shuffle=(train_sampler is None))

    file_name = "./models/" + args.Architecture.lower()
    visplots = VisPlots(file_name.split("/")[-1].split(".")[0])
    Model = MakeModel(file_name,
                      tensor_size,
                      n_labels,
                      embedding_net=core.NeuralArchitectures.CapsuleNet,
                      embedding_net_kwargs={"replicate_paper": True},
                      loss_net=core.NeuralLayers.CapsuleLoss,
                      loss_net_kwargs={},
                      default_gpu=args.default_gpu,
                      gpus=0,  # Need to make sure DataParallel is off
                      ignore_trained=args.ignore_trained)
    Model.netEmbedding.to('cuda')
    Model.netEmbedding = DistributedDataParallel(Model.netEmbedding, device_ids=[args.local_rank], output_device=args.local_rank)

    params = list(Model.netEmbedding.parameters()) + \
        list(Model.netLoss.parameters())
    if args.optimizer.lower() == "adam":
        Optimizer = torch.optim.Adam(params)
    elif args.optimizer.lower() == "sgd":
        Optimizer = torch.optim.SGD(params, lr=args.learningRate)
    else:
        raise NotImplementedError

    # Usual training
    for epoch in range(args.Epochs):
        train_sampler.set_epoch(epoch)
        Timer = timeit.default_timer()
        Model.netEmbedding.train()
        Model.netLoss.train()
        for i, (tensor, targets) in enumerate(trData):
            Model.meterIterations += 1

            # forward pass and parameter update
            Model.netEmbedding.zero_grad()
            Model.netLoss.zero_grad()
            features, rec_tensor, rec_loss = \
                Model.netEmbedding((tensor, targets))
            margin_loss, (top1, top5) = Model.netLoss((features, targets))
            loss = margin_loss + 0.0005*rec_loss/features.size(0)
            loss.backward()
            Optimizer.step()

            # weight visualization
            if i % 50 == 0:
                visplots.show_weights(Model.netEmbedding.state_dict(),
                                      png_name=file_name)

            # updating all meters
            Model.meterTop1.append(float(top1.cpu().data.numpy()))
            Model.meterTop5.append(float(top5.cpu().data.numpy()))
            Model.meterLoss.append(float(loss.cpu().data.numpy()))

            Model.meterSpeed.append(int(float(args.BSZ) /
                                        (timeit.default_timer()-Timer)))
            Timer = timeit.default_timer()

            print("... {:6d} :: ".format(Model.meterIterations) +
                  "Cost {:2.3f} :: ".format(Model.meterLoss[-1]) +
                  "Top1/Top5 - {:3.2f}/{:3.2f}".format(Model.meterTop1[-1],
                                                       Model.meterTop5[-1],) +
                  " :: {:4d} I/S    ".format(Model.meterSpeed[-1]), end="\r")
            sys.stdout.flush()

        # save every epoch and print the average of epoch
        mean_loss = np.mean(Model.meterLoss[-i:])
        mean_top1 = np.mean(Model.meterTop1[-i:])
        mean_top5 = np.mean(Model.meterTop5[-i:])
        mean_speed = int(np.mean(Model.meterSpeed[-i:]))
        print("... {:6d} :: ".format(Model.meterIterations) +
              "Cost {:2.3f} :: ".format(mean_loss) +
              "Top1/Top5 - {:3.2f}/{:3.2f}".format(mean_top1, mean_top5) +
              " :: {:4d} I/S    ".format(mean_speed))
        # save model
        SaveModel(Model)

        test_top1, test_top5 = [], []
        Model.netEmbedding.eval()
        Model.netLoss.eval()
        for i, (tensor, targets) in enumerate(teData):
            features, rec_tensor, rec_loss = \
                Model.netEmbedding((tensor, targets))
            margin_loss, (top1, top5) = Model.netLoss((features, targets))
            test_top1.append(float(top1.cpu().data.numpy()))
            test_top5.append(float(top5.cpu().data.numpy()))
        print("... Test accuracy - {:3.2f}/{:3.2f}".format(np.mean(test_top1),
                                                           np.mean(test_top5)))
        Model.netEmbedding.train()
        Model.netLoss.train()
        Timer = timeit.default_timer()

    print("\nDone with training")
    return Model


if __name__ == '__main__':
    Model = trainMONK()
