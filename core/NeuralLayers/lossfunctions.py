""" TensorMONK's :: NeuralLayers :: LossFunctions                           """

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from torch.autograd.function import Function
# =========================================================================== #


def compute_n_embedding(tensor_size):
    if isinstance(tensor_size, list) or isinstance(tensor_size, tuple):
        if len(tensor_size) > 1:  # batch size is not required
            tensor_size = np.prod(tensor_size[1:])
        else:
            tensor_size = tensor_size[0]
    return int(tensor_size)


def compute_top15(responses, targets):
    predicted = responses.topk(5, 1, True, True)[1]
    predicted = predicted.t()
    correct = predicted.eq(targets.view(1, -1).expand_as(predicted))
    top1 = correct[:1].view(-1).float().sum().mul_(100.0 / responses.size(0))
    top5 = correct[:5].view(-1).float().sum().mul_(100.0 / responses.size(0))
    return top1, top5


def one_hot(targets, n_labels):
    identity = torch.eye(n_labels).to(targets.device)
    onehot_targets = identity.index_select(dim=0,
                                           index=targets.long().view(-1))
    return onehot_targets.requires_grad_()


def one_hot_idx(targets, n_labels):
    targets = targets.view(-1)
    return targets + \
        torch.arange(0, targets.size(0)).to(targets.device) * n_labels


def nlog_likelihood(tensor, targets):
    return F.nll_loss(tensor.log_softmax(1), targets)
# =========================================================================== #


def hardest_negative(lossValues, margin):
    return lossValues.max(2)[0].max(1)[0].mean()


def semihard_negative(lossValues, margin):
    lossValues = torch.where((torch.ByteTensor(lossValues > 0.) &
                              torch.ByteTensor(lossValues < margin)),
                             lossValues, torch.zeros(lossValues.size()))
    return lossValues.max(2)[0].max(1)[0].mean()


class TripletLoss(nn.Module):
    def __init__(self, margin, negative_selection_fn='hardest_negative',
                 samples_per_class=2, *args, **kwargs):
        super(TripletLoss, self).__init__()
        self.tensor_size = (1,)
        self.margin = margin
        self.negative_selection_fn = negative_selection_fn
        self.sqrEuc = lambda x: (x.unsqueeze(0) -
                                 x.unsqueeze(1)).pow(2).sum(2).div(x.size(1))
        self.perclass = samples_per_class

    def forward(self, embeddings, labels):
        labels = torch.from_numpy(np.array([1, 1, 0, 1, 1], dtype='float32'))
        InClass = labels.reshape(-1, 1) == labels.reshape(1, -1)
        Consider = torch.eye(labels.size(0)).mul(-1).add(1) \
                        .type(InClass.type())
        Scores = self.sqrEuc(embeddings)

        Gs = Scores.view(-1, 1)[(InClass*Consider).view(-1, 1)] \
            .reshape(-1, self.perclass-1)
        Is = Scores.view(-1, 1)[(InClass == 0).view(-1, 1)] \
            .reshape(-1, embeddings.size(0)-self.perclass)

        lossValues = Gs.view(embeddings.size(0), -1, 1) - \
            Is.view(embeddings.size(0), 1, -1) + self.margin
        lossValues = lossValues.clamp(0.)

        if self.negative_selection_fn == "hardest_negative":
            return hardest_negative(lossValues, self.margin), Gs, Is
        elif self.negative_selection_fn == "semihard_negative":
            return semihard_negative(lossValues, self.margin), Gs, Is
        else:
            raise NotImplementedError
# =========================================================================== #


class DiceLoss(nn.Module):
    r""" Dice/ Tversky loss for semantic segmentationself.
    Implemented from https://arxiv.org/pdf/1803.11078.pdf
    https://arxiv.org/pdf/1706.05721.pdf has same equation but with alpha
    and beta controlling FP and FN.
    Args:
        type: tversky/dice
    Definations:
        p_i - correctly predicted foreground pixels
        p_j - correctly predicted background pixels
        g_i - target foreground pixels
        g_j - target background pixels
        p_i * g_i - True Positives  (TP)
        p_i * g_j - False Positives (FP)
        p_j * g_i - False Negatives (FN)
    """
    def __init__(self, type="tversky", *args, **kwargs):
        super(DiceLoss, self).__init__()
        self.tensor_size = (1,)
        if type == "tversky":
            self.beta = 2.0
            # for https://arxiv.org/pdf/1706.05721.pdf,
            # beta of 2 results in alpha of 0.2 and beta of 0.8
        elif type == "dice":
            self.beta = 1.0         # below Eq(6)
        else:
            raise NotImplementedError

    def forward(self, prediction, targets):
        top1, top5 = 0., 0.
        if prediction.shape[1] == 1:
            p_i = prediction
            p_j = prediction.mul(-1).add(1)
            g_i = targets
            g_j = targets.mul(-1).add(1)
            # the above is similar to one hot encoding of targets
            num = (p_i*g_i).sum(1).sum(1).mul((1 + self.beta**2))   # eq(5)
            den = num.add((p_i*g_j).sum(1).sum(1).mul((self.beta**2))) \
                .add((p_j*g_i).sum(1).sum(1).mul((self.beta)))    # eq(5)
            loss = num / den.add(1e-6)
        elif prediction.shape[1] == 2:
            p_i = prediction[:, 0, :, :]
            p_j = prediction[:, 1, :, :]
            g_i = targets
            g_j = targets.mul(-1).add(1)
            # the above is similar to one hot encoding of targets
            num = (p_i*g_i).sum(1).sum(1).mul((1 + self.beta**2))   # eq(5)
            den = num.add((p_i*g_j).sum(1).sum(1).mul((self.beta**2))) \
                .add((p_j*g_i).sum(1).sum(1).mul((self.beta)))    # eq(5)
            loss = num / den.add(1e-6)
        else:
            raise NotImplementedError
        return loss.mean(), (top1, top5)
# =========================================================================== #


class CapsuleLoss(nn.Module):
    r""" For Dynamic Routing Between Capsules.
    Implemented  https://arxiv.org/pdf/1710.09829.pdf
    """
    def __init__(self, n_labels, *args, **kwargs):
        super(CapsuleLoss, self).__init__()
        self.n_labels = n_labels
        self.tensor_size = (1,)

    def forward(self, tensor, targets):
        onehot_targets = one_hot(targets, self.n_labels)
        # L2
        predictions = tensor.pow(2).sum(2).add(1e-6).pow(.5)
        # m+, m-, lambda, Tk all set per paper
        loss = onehot_targets*((.9 - predictions).clamp(0, 1e6)**2) + \
            (1 - onehot_targets)*.5 * ((predictions - .1).clamp(0, 1e6)**2)

        (top1, top5) = compute_top15(predictions.data, targets.data)
        return loss.sum(1).mean(), (top1, top5)
# =========================================================================== #


class CategoricalLoss(nn.Module):
    r""" CategoricalLoss with weight's to convert embedding to n_labels
    categorical responses.

    Args:
        tensor_size (int/list/tuple): shape of tensor in
            (None/any integer >0, channels, height, width) or
            (None/any integer >0, in_features) or in_features
        n_labels (int): number of labels
        type (str): loss function, options = entr/smax/tsmax/lmcl,
            default = entr
            entr  - categorical cross entropy
            smax  - softmax + negative log likelihood
            tsmax - taylor softmax + negative log likelihood
                 https://arxiv.org/pdf/1511.05042.pdf
            lmcl  - large margin cosine loss
                 https://arxiv.org/pdf/1801.09414.pdf  eq-4
            lmgm  - large margin Gaussian Mixture
                 https://arxiv.org/pdf/1803.02988.pdf  eq-17
        measure (str): cosine/dot, cosine similarity / matrix dot product,
            default = dot
        center (bool): center loss https://ydwen.github.io/papers/WenECCV16.pdf
        scale (float): lambda in center loss / lmgm / s in lcml, default = 0.5
        margin (float): margin for lcml, default = 0.3
        alpha (float): center or lmgm, default = 0.5
        defaults (float): deafults center, lcml, & lmgm parameters

    Return:
        loss, (top1, top5)
    """
    def __init__(self,
                 tensor_size,
                 n_labels,
                 type: str = "entr",
                 measure: str = "dot",
                 center: bool = False,
                 scale: float = 0.5,
                 margin: float = 0.3,
                 alpha: float = 0.5,
                 defaults: bool = False,
                 *args, **kwargs):
        super(CategoricalLoss, self).__init__()

        n_embedding = compute_n_embedding(tensor_size)
        self.type = type.lower()
        if "distance" in kwargs.keys():  # add future warning
            measure = kwargs["distance"]
        self.measure = measure.lower()
        assert self.type in ("entr", "smax", "tsmax", "lmcl", "lmgm"), \
            "CategoricalLoss :: type != entr/smax/tsmax/lmcl/lmgm"
        assert self.measure in ("dot", "cosine"), \
            "CategoricalLoss :: measure != dot/cosine"

        if defaults:
            if self.type == "lmcl":
                margin, scale = 0.35, 10
            if center:
                scale, alpha = 0.5, 0.01
            if self.type == "lmgm":
                alpha, scale = 0.01, 0.1

        self.center = center
        if center:
            self.register_buffer("center_alpha", torch.Tensor([alpha]).sum())
            self.centers = nn.Parameter(
                F.normalize(torch.randn(n_labels, n_embedding), p=2, dim=1))
            self.center_function = CenterFunction.apply

        self.scale = scale
        self.margin = margin
        self.alpha = alpha
        self.n_labels = n_labels

        self.weight = nn.Parameter(torch.randn(n_labels, n_embedding))
        self.tensor_size = (1, )

    def forward(self, tensor, targets):

        if self.type == "lmgm":
            # TODO euclidean computation is not scalable to larger n_labels
            # mahalanobis with identity covariance per paper = squared
            # euclidean -- does euclidean for stability
            # Switch to measure="cosine" if you have out of memory issues
            if self.measure == "cosine":
                self.weight.data = F.normalize(self.weight.data, p=2, dim=1)
                tensor = F.normalize(tensor, p=2, dim=1)
                responses = 1 - tensor.mm(self.weight.t())
            else:
                responses = (tensor.unsqueeze(1) - self.weight.unsqueeze(0))
                responses = responses.pow(2).sum(2).pow(0.5)
            (top1, top5) = compute_top15(- responses.data, targets.data)

            true_idx = one_hot_idx(targets, self.n_labels)
            responses = responses.view(-1)
            loss = self.scale * (responses[true_idx]).mean()
            responses[true_idx] = responses[true_idx] * (1 + self.alpha)
            loss = loss + nlog_likelihood(- responses.view(tensor.size(0), -1),
                                          targets)
            return loss, (top1, top5)

        if self.measure == "cosine" or self.type == "lmcl":
            self.weight.data = F.normalize(self.weight.data, p=2, dim=1)
            tensor = F.normalize(tensor, p=2, dim=1)
        responses = tensor.mm(self.weight.t())
        if self.measure == "cosine" or self.type == "lmcl":
            responses = responses.clamp(-1., 1.)
        (top1, top5) = compute_top15(responses.data, targets.data)

        if self.type == "tsmax":  # Taylor series
            responses = 1 + responses + 0.5*(responses**2)

        if self.type == "entr":
            loss = F.cross_entropy(responses, targets.view(-1))

        elif self.type in ("smax", "tsmax"):
            loss = nlog_likelihood(responses, targets)

        elif self.type == "lmcl":
            m, s = min(0.5, self.margin), max(self.scale, 1.)
            true_idx = one_hot_idx(targets, self.n_labels)
            responses = responses.view(-1)
            responses[true_idx] = responses[true_idx] - m
            responses = (responses * s).view(tensor.size(0), -1)
            loss = nlog_likelihood(responses, targets)
        else:
            raise NotImplementedError

        if self.center:
            loss = loss + self.center_function(tensor, targets.long(),
                                               self.centers, self.center_alpha)

        return loss, (top1, top5)


class CenterFunction(Function):

    @staticmethod
    def forward(ctx, tensor, targets, centers, alpha):
        ctx.save_for_backward(tensor, targets, centers, alpha)
        target_centers = centers.index_select(0, targets)
        return 0.5 * (tensor - target_centers).pow(2).sum()

    @staticmethod
    def backward(ctx, grad_output):

        tensor, targets, centers, alpha = ctx.saved_variables
        grad_tensor = grad_centers = None
        grad_centers = torch.zeros(centers.size()).to(tensor.device)
        grad_tensor = tensor - centers.index_select(0, targets.long())

        unique = torch.unique(targets.long())
        for j in unique:
            grad_centers[j] += centers[j] - \
                tensor.data[targets == j].mean(0).mul(alpha)

        return grad_tensor * grad_output, None, grad_centers, None


# tensor = torch.rand(3, 256)
# test = CategoricalLoss(256, 10, "smax", center=True)
# targets = torch.tensor([1, 3, 6])
# test(tensor, targets)
