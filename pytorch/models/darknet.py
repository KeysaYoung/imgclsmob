"""
    DarkNet, implemented in PyTorch.
    Original paper: 'Darknet: Open source neural networks in c'
"""

__all__ = ['DarkNet', 'darknet_ref', 'darknet_tiny', 'darknet19']

import torch
import torch.nn as nn
import torch.nn.init as init


class DarkConv(nn.Module):

    def __init__(self,
                 in_channels,
                 out_channels,
                 kernel_size,
                 padding):
        super(DarkConv, self).__init__()
        self.conv = nn.Conv2d(
            in_channels=in_channels,
            out_channels=out_channels,
            kernel_size=kernel_size,
            padding=padding,
            bias=False)
        self.bn = nn.BatchNorm2d(num_features=out_channels)
        #self.bn = nn.BatchNorm2d(num_features=out_channels, momentum=0.01)
        self.activ = nn.LeakyReLU(
            negative_slope=0.1,
            inplace=True)

    def forward(self, x):
        x = self.conv(x)
        x = self.bn(x)
        x = self.activ(x)
        return x


def dark_conv1x1(in_channels,
                 out_channels):
    return DarkConv(
        in_channels=in_channels,
        out_channels=out_channels,
        kernel_size=1,
        padding=0)


def dark_conv3x3(in_channels,
                 out_channels):
    return DarkConv(
        in_channels=in_channels,
        out_channels=out_channels,
        kernel_size=3,
        padding=1)


def dark_convYxY(in_channels,
                 out_channels,
                 pointwise=True):
    if pointwise:
        return dark_conv1x1(
            in_channels=in_channels,
            out_channels=out_channels)
    else:
        return dark_conv3x3(
            in_channels=in_channels,
            out_channels=out_channels)


class DarkNet(nn.Module):

    def __init__(self,
                 channels,
                 odd_pointwise,
                 avg_pool_size,
                 cls_activ,
                 in_channels=3,
                 num_classes=1000):
        super(DarkNet, self).__init__()

        self.features = nn.Sequential()
        for i, channels_per_stage in enumerate(channels):
            stage = nn.Sequential()
            for j, out_channels in enumerate(channels_per_stage):
                stage.add_module("unit{}".format(j + 1), dark_convYxY(
                    in_channels=in_channels,
                    out_channels=out_channels,
                    pointwise=(len(channels_per_stage) > 1) and not (((j + 1) % 2 == 1) ^ odd_pointwise)))
                in_channels = out_channels
            if i != len(channels) - 1:
                stage.add_module("pool{}".format(i + 1), nn.MaxPool2d(
                    kernel_size=2,
                    stride=2))
            self.features.add_module("stage{}".format(i + 1), stage)

        self.output = nn.Sequential()
        self.output.add_module('final_conv', nn.Conv2d(
            in_channels=in_channels,
            out_channels=num_classes,
            kernel_size=1))
        if cls_activ:
            self.output.add_module('final_activ', nn.LeakyReLU(
            negative_slope=0.1,
            inplace=True))
        self.output.add_module('final_pool', nn.AvgPool2d(
            kernel_size=avg_pool_size,
            stride=1))

        self._init_params()

    def _init_params(self):
        for name, module in self.named_modules():
            if isinstance(module, nn.Conv2d):
                if 'final_conv' in name:
                    init.normal_(module.weight, mean=0.0, std=0.01)
                else:
                    init.kaiming_uniform_(module.weight)
                if module.bias is not None:
                    init.constant_(module.bias, 0)

    def forward(self, x):
        x = self.features(x)
        x = self.output(x)
        x = x.view(x.size(0), -1)
        return x


def get_darknet(version,
                pretrained=False,
                **kwargs):
    if version == 'ref':
        channels = [[16], [32], [64], [128], [256], [512], [1024]]
        odd_pointwise = False
        avg_pool_size = 3
        cls_activ = True
    elif version == 'tiny':
        channels = [[16], [32], [16, 128, 16, 128], [32, 256, 32, 256], [64, 512, 64, 512, 128]]
        odd_pointwise = True
        avg_pool_size = 14
        cls_activ = False
    elif version == '19':
        channels = [[32], [64], [128, 64, 128], [256, 128, 256], [512, 256, 512, 256, 512], [1024, 512, 1024, 512, 1024]]
        odd_pointwise = False
        avg_pool_size = 7
        cls_activ = False
    else:
        raise ValueError("Unsupported DarkNet version {}".format(version))

    if pretrained:
        raise ValueError("Pretrained model is not supported")

    return DarkNet(
        channels=channels,
        odd_pointwise=odd_pointwise,
        avg_pool_size=avg_pool_size,
        cls_activ=cls_activ,
        **kwargs)


def darknet_ref(**kwargs):
    return get_darknet('ref', **kwargs)


def darknet_tiny(**kwargs):
    return get_darknet('tiny', **kwargs)


def darknet19(**kwargs):
    return get_darknet('19', **kwargs)


def _test():
    import numpy as np
    from torch.autograd import Variable

    global TESTING
    TESTING = True

    models = [
        darknet_ref,
        darknet_tiny,
        darknet19,
    ]

    for model in models:

        net = model()

        net.train()
        net_params = filter(lambda p: p.requires_grad, net.parameters())
        weight_count = 0
        for param in net_params:
            weight_count += np.prod(param.size())
        assert (model != darknet_ref or weight_count == 7319416)
        assert (model != darknet_tiny or weight_count == 1042104)
        assert (model != darknet19 or weight_count == 20842376)

        x = Variable(torch.randn(1, 3, 224, 224))
        y = net(x)
        assert (tuple(y.size()) == (1, 1000))


if __name__ == "__main__":
    _test()

