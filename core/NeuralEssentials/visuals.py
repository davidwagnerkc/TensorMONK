""" TensorMONK's :: NeuralEssentials                                        """

import sys
import torch
import torch.nn.functional as F
import torchvision.utils as tutils
import imageio
import visdom
if sys.version_info.major == 3:
    from functools import reduce
# =========================================================================== #


def MakeGIF(image_list, gif_name):
    r"""Makes a gif using a list of images.
    """
    if not gif_name.endswith(".gif"):
        gif_name += ".gif"
    imageio.mimsave(gif_name, [imageio.imread(x) for x in image_list])
# =========================================================================== #


class VisPlots(object):
    r"""Visdom plots to monitor weights (histograms and 2D kernels larger than
    3x3), and responses.

    Args:
        env: name of your environment, default = main
        server: server address, default = None
    """
    def __init__(self, env="main", server=None):
        if server is None:
            self.visplots = visdom.Visdom(env=env)
        else:
            self.visplots = visdom.Visdom(env=env, server=server)

    def histograms(self, data, vis_name="hist"):
        r""" Plots histograms of weights. For Model.state_dict(), parameter
        names after used to name the plots.

        Args:
            data: Accepts nn.Parameter, torch.Tensor and Model.state_dict()
            vis_name: required for nn.Parameter, and torch.Tensor,
                default = "hist"
        """
        if isinstance(data, dict):
            # parameter generator (essentially, model.state_dict())
            for p in data.keys():
                if "weight" in p and "weight_g" not in p and \
                   "Normalization" not in p and "bias" not in p:

                    # ignore normalization weights (gamma's & beta's) and bias
                    newid = self._trim_name(p)
                    self.visplots.histogram(X=data[p].data.cpu().view(-1),
                                            opts={"numbins": 46,
                                                  "title": newid},
                                            win=newid)
        elif (isinstance(data, torch.nn.parameter.Parameter) or
              isinstance(data, torch.Tensor)):
            # pytorch tensor or parameter
            self.visplots.histogram(X=data.data.cpu().view(-1),
                                    opts={"numbins": 46, "title": vis_name},
                                    win=vis_name)
        else:
            raise NotImplementedError

    def show_images(self, data, vis_name="images", png_name=None,
                    normalize=False, height=None, max_samples=512,
                    attention=False):
        r""" Plots responses in RGB (C=3) and grey (C=1), requires BCHW
        torch.Tensor. When C != 1/3, reorganizes the BxCxHxW to BCx1xHxC if
        attention is False, else Bx1xHxC.

        Args:
            data: 4D torch.Tensor
            vis_name: name for visdom plots, default = "images"
            png_name: used to save png images, default = None
            normalize: normalized the range to 0-1
            height: max height of image, retains aspect ratio. default = None
            max_samples: limited to speed ploting, default = 512
            attention: computes attention BxCxHxW to Bx1xHxC using l2,
                normalize is applied default = False
        """
        if isinstance(data, torch.Tensor):
            if data.dim() != 4:
                return None
            # pytorch tensor
            data = data.data.cpu()
            if attention:
                data = data.pow(2).sum(1, True).pow(.5)
            if normalize or attention:  # adjust range to 0-1
                data = self._normalize_01(data)
            # adjust 4d tensor and reduce samples when too many
            sz = data.size()
            multiplier = 1
            if sz[1] not in [1, 3]:  # BxCxHxW to BCx1xHxC
                data = data.view(-1, 1, *sz[2:])
                multiplier = sz[1]
            if sz[0]*multiplier > max_samples:
                samples = reduce(lambda x, y: max(x, y),
                                 [x*multiplier for x in range(sz[0]) if
                                  x*multiplier <= max_samples])
                data = data[:samples]
            # resize image when height is not None
            if height is not None:
                sz = (height, int(float(height)*sz[3]/sz[2]))
                data = F.interpolate(data, size=sz)
            self.visplots.images(data, nrow=max(4, int(data.size(0)**0.5)),
                                 opts={"title": vis_name}, win=vis_name)
            # save a png if png_name is defined
            if png_name is not None:
                tutils.save_image(data, png_name)

    def show_weights(self, data, vis_name="weights", png_name=None,
                     min_width=3, max_samples=512):
        r""" Plots weights (histograms and images of 2D kernels larger than
        min_width). 2D kernels are normalized between 0-1 for visualization.
        Requires a minimum of 4 kernels to plot images.

        Args:
            data: Accepts nn.Parameter, torch.Tensor and Model.state_dict()
            vis_name: name for visdom plots, default = "weights"
            png_name: used to save png images, default = None
            min_width: only plots images if the kernel size width and height is
                above min_width
            max_samples: limited to speed ploting, default = 512
        """
        # all histograms
        self.histograms(data, vis_name)
        # only convolution weights when kernel size > 3
        n = 0
        if isinstance(data, dict):
            # parameter generator (essentially, model.state_dict())
            for p in data.keys():
                if data[p].dim() == 4 and data[p].size(2) > min_width and \
                   data[p].size(3) > min_width:
                    pass
                    newid = self._trim_name(p)
                    ws = data[p].data.cpu()
                    sz = ws.size()
                    if sz[1] not in [1, 3]:
                        ws = ws.view(-1, 1, sz[2], sz[3])
                        sz = ws.size()
                    if 4 < sz[0] <= max_samples:
                        ws = self._normalize_01(ws)
                        self.visplots.images(ws, nrow=max(4, int(sz[0]**0.5)),
                                             opts={"title": "Ws-"+newid},
                                             win="Ws-"+newid)
                    if png_name is not None:
                        tutils.save_image(ws, png_name.rstrip(".png") +
                                          "-ws{}".format(n) + ".png")
                        n += 1
        elif isinstance(data, torch.nn.parameter.Parameter):
            # pytorch parameter
            if data.dim() == 4 and data.size(2) > min_width and \
               data.size(3) > min_width:
                data = data.data.cpu()
                sz = data.size()
                if sz[1] not in [1, 3]:
                    data = data.view(-1, 1, sz[2], sz[3])
                    sz = data.size()
                if sz[0] <= max_samples:
                    data = self._normalize_01(data)
                    self.visplots.images(data, nrow=max(4, int(sz[0]**0.5)),
                                         opts={"title": "Ws-"+vis_name},
                                         win="Ws-"+vis_name)
                if png_name is not None:
                    tutils.save_image(data, png_name.rstrip(".png") + "-ws-" +
                                      vis_name + ".png")
        else:
            raise NotImplementedError

    def _normalize_01(self, tensor):
        _min = tensor.min(2, True)[0].min(3, True)[0]
        _max = tensor.max(2, True)[0].max(3, True)[0]
        return tensor.add(-_min).div(_max - _min + 1e-6)

    @staticmethod
    def _trim_name(name):
        return name.replace("NET46.", "").replace("Net46.",
                                                  "") .replace("network.", "")


# visplots = VisPlots()
# hasattr(visplots, "visplots")
# visplots.show_images(torch.rand(10, 10, 200, 200), height=32)
# visplots.show_weights(torch.nn.Parameter(torch.rand(10, 10, 7, 7)))
