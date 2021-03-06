# TensorMONK

A collection of deep learning architectures (a PyTorch implementation).

## Dependencies
* python 3.6
* PyTorch > 0.4.1
* torchvision
* visdom

## How to train ImageNet?

If you have more nvidia graphic cards & cores available, adjust the batch size (BSZ), number of GPUs (gpus), & number of threads (cpus) accordingly in the ./ImageNet.sh. Next, select an available architecture and update your train & validation folder location (trainDataPath and testDataPath). Finally, run ./ImageNet.sh.

## How to train CapsuleNet?

To replicate Hinton's paper on MNIST, run the following:

python Capsule.py -A capsule -B 256 -E 500 --optimizer adam --gpus 2 --cpus 6 --trainDataPath ./data --testDataPath ./data --replicate_paper

Ignore the replicate_paper argument to create a deep architecture (with few residual blocks before primary capsule). You can essentially add any block available in NeuralLayers to create a deeper architecture, which is followed by a primary capsule and secondary capsule. However, do consider two things 1. if you do reconstruction, update the reconstruction network relative to tensor_size, 2. capsule nets do require a good amount of gpu ram.

## Generative Adversarial Networks GAN

### [Progressive Growing of GANs](https://arxiv.org/pdf/1710.10196.pdf)

Trained on CIFAR10 (pggan-cifar10.py) -- requires more training (more gpus)!

![Generator at 4x4](https://github.com/Tensor46/TensorMONK/blob/develop/models/pggan-cifar10-level1.gif)
![Generator at 8x8](https://github.com/tensor46/TensorMONK/blob/develop/models/pggan-cifar10-level2.gif)
![Generator at 16x16](https://github.com/tensor46/TensorMONK/blob/develop/models/pggan-cifar10-level3.gif)
![Generator at 32x32](https://github.com/tensor46/TensorMONK/blob/develop/models/pggan-cifar10-level4.gif)

## Details on core (NeuralArchitectures, NeuralEssentials, NeuralLayers)

### NeuralArchitectures
* ResidualNet -- use type = [r18/r34/r50/r101/r152](https://arxiv.org/pdf/1512.03385.pdf) or [rn50/rn101/rn152 for ResNeXt](https://arxiv.org/pdf/1611.05431.pdf) or [ser50/ser101/ser152 for Squeeze-and-Excitation Networks](https://arxiv.org/pdf/1709.01507.pdf) or sern50/sern101/sern152 (ResNeXt + Squeeze-and-Excitation Networks). Pretrained weights are available for r18, r34, r50, r101, & r152.
* [DenseNet](https://arxiv.org/pdf/1608.06993.pdf) -- use type (see Table 1 in paper) - d121/d169/d201/d264. Pretrained weights are available for d121, d169, & d201.
* [InceptionV4](https://arxiv.org/pdf/1602.07261.pdf)
* [MobileNetV1](https://arxiv.org/pdf/1704.04861.pdf)
* [MobileNetV2](https://arxiv.org/pdf/1801.04381.pdf)
* [ShuffleNet](https://arxiv.org/pdf/1707.01083.pdf) (type = g1, g2, g3, g4, g8 from table 1)
* [CapsuleNet](https://arxiv.org/pdf/1710.09829.pdf) (Hinton's version, and an example deep network)
* [LinearVAE](https://arxiv.org/pdf/1312.6114v10.pdf)
* [ConvolutionalVAE](https://arxiv.org/pdf/1312.6114v10.pdf)
* SimpleNet
* [PGGAN](https://arxiv.org/pdf/1710.10196.pdf)
* [ContextNet](https://arxiv.org/pdf/1805.04554.pdf) (bottleneck layer of ContextNet is implemented in NeuralLayers/CarryResidue/)
* [PointNet](http://openaccess.thecvf.com/content_cvpr_2017/papers/Zhang_Learning_Discriminative_and_CVPR_2017_paper.pdf)
* [UNet](https://arxiv.org/pdf/1505.04597.pdf)
  * UNetPatch -- Works on small patches.
* [NeuralDecisionForest](https://www.cv-foundation.org/openaccess/content_iccv_2015/papers/Kontschieder_Deep_Neural_Decision_ICCV_2015_paper.pdf)

### NeuralEssentials
* BaseModel -- A base class that contains networks (embedding, loss or any), meters (loss, accuracy etc), fileName, isCUDA
* CudaModel -- Converts any model (pytorch module) to run on single gpu or multiple gpu's or cpu
* LoadModel -- Loads pretrained models (usually, from ./models)
* SaveModel -- Save models (usually, state_dict of anything that starts with net in BaseModel, and rest as is)
* MakeModel -- Builds model using base class
  * MakeCNN -- Creates a CNN (netEmbedding) and loss layer (netLoss)
  * MakeAE -- Creates an auto-encoder/vae in netAE
* FolderITTR -- PyTorch image folder iterator with few extras.
* MNIST -- MNIST train and test dataset loader
* CIFAR10 -- CIFAR10 train and test dataset loader
* MakeGIF -- Given a list of images creates a gif
* VisPlots -- Visdom wrapper to visualize weight histograms, responses, and weights (see SimpleMNIST.py)


### NeuralLayers

* Convolution -- A convolution layer with following parameters:
  * tensor_size = a list/tuple of length 4 (BxWxHxC - any B should work)
  * filter_size = int/list/tuple (if list/tuple, length must be 2)
  * out_channels = int
  * strides = int/list/tuple (if list/tuple, length must be 2)
  * pad = True/False (True essentially delivers same output size when strides = 1, and False returns valid convolution)
  * activation = relu/relu6/lklu(leaky relu)/tanh/sigm/[maxo](https://arxiv.org/pdf/1302.4389.pdf)/[swish](https://arxiv.org/pdf/1710.05941v1.pdf)
  * dropout = 0. to 1. (adds dropout layer)
  * normalization = None/"batch"/"group"/"instance"/"layer"/"pixelwise"
  * pre_nm = True/False (when True along with normalization = "batch" -- batch normalization + activation + convolution else convolution + batch normalization + activation)
  * groups = 1 (default)
  * [weight_nm](https://arxiv.org/pdf/1602.07868.pdf) = True/False
  * [equalized](https://arxiv.org/pdf/1710.10196.pdf) = True/False
  * [shift](https://arxiv.org/pdf/1711.08141.pdf) = True/False -- requires 3x3 kernel, and a minimum #channels of input >= 9


* ConvolutionTranspose -- A convolution transpose layer with parameters same as Convolution layer

* CarryResidue -- Has several layers that requires residual connections or concatenation
  * [ResidualOriginal](https://arxiv.org/pdf/1512.03385.pdf)
  * [ResidualComplex](https://arxiv.org/pdf/1512.03385.pdf)
  * [ResidualNeXt](https://arxiv.org/pdf/1611.05431.pdf)
  * [SEResidualComplex](https://arxiv.org/pdf/1709.01507.pdf)
  * SEResidualNeXt
  * [ResidualInverted](https://arxiv.org/pdf/1801.04381.pdf)
  * [ResidualShuffle](https://arxiv.org/pdf/1707.01083.pdf)
  * [SimpleFire](https://arxiv.org/pdf/1602.07360.pdf)
  * [DenseBlock](https://arxiv.org/pdf/1608.06993.pdf)
  * [Stem2](https://arxiv.org/pdf/1602.07261.pdf)
  * [InceptionA](https://arxiv.org/pdf/1602.07261.pdf)
  * [InceptionB](https://arxiv.org/pdf/1602.07261.pdf)
  * [InceptionC](https://arxiv.org/pdf/1602.07261.pdf)
  * [ReductionA](https://arxiv.org/pdf/1602.07261.pdf)
  * [ReductionB](https://arxiv.org/pdf/1602.07261.pdf)
  * [ContextNet_Bottleneck](https://arxiv.org/pdf/1805.04554.pdf)

* [DropBlock](https://arxiv.org/abs/1810.12890)
* [PrimaryCapsule](https://arxiv.org/pdf/1710.09829.pdf)
* [RoutingCapsule](https://arxiv.org/pdf/1710.09829.pdf)

* LossFunctions
  * [CapsuleLoss](https://arxiv.org/pdf/1710.09829.pdf)
  * CategoricalLoss -- Cross entropy / softmax / [taylor softmax](https://arxiv.org/pdf/1511.05042.pdf) / [large margin cosine loss](https://arxiv.org/pdf/1801.09414.pdf) / [large-margin Gaussian Mixture](https://arxiv.org/pdf/1803.02988.pdf)
  * [CenterLoss](https://ydwen.github.io/papers/WenECCV16.pdf)
  * TripletLoss
  * [DiceLoss / Tversky Loss](https://arxiv.org/abs/1706.05721)
