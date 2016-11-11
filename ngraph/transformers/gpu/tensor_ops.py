# ----------------------------------------------------------------------------
# Copyright 2016 Nervana Systems Inc.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ----------------------------------------------------------------------------

from ngraph.transformers.gpu.kernel import GPUKernel, pointer_from_td
from ngraph.transformers.gpu.float_ew2 import TensorDescriptionWrapper
from ngraph.op_graph.axes import TensorDescription

from neon.backends.convolution import _get_copy_transpose_kernel


class DimShuffleKernel(GPUKernel):
    def __init__(self, transformer, op):
        super(DimShuffleKernel, self).__init__(transformer)

        out = TensorDescriptionWrapper(op.tensor_description(), 2)
        (arg, ) = (_ for _ in op.call_info())
        in_tensor = TensorDescriptionWrapper(arg, 2)

        dtype = out.dtype.str
        shape = in_tensor.shape
        axes = op.old_axis_positions

        self.kernel = _get_copy_transpose_kernel(dtype, shape, axes)
        self.params = [out.td, in_tensor.td] + list(self.kernel.args)
        self.params = self.params + list(in_tensor.strides) + list(out.strides)

    def bind_buffers(self):
        """
        Binds GPU addresses of buffers to the kernel parameters. When kernels
        and initial parameters are generated, tensors have not yet been
        allocated so a placeholder is used for the memory addresses. This must
        be called before the first kernel run to bind the tensor addresses in
        GPU memory to the kernel parameters.
        """
        for index in range(len(self.params)):
            if isinstance(self.params[index], TensorDescription):
                self.params[index] = pointer_from_td(self.params[index])

        super(DimShuffleKernel, self).bind_buffers()

    def execute(self):
        self.kernel.prepared_async_call(self.kernel.grid, self.kernel.block,
                                        None, *self.params)


class FillKernel(GPUKernel):
    def __init__(self, transformer, td, value):
        super(FillKernel, self).__init__(transformer)

        self.value = value
        self.out = td

    def bind_buffers(self):
        self.out = self.out.value.tensor
        super(FillKernel, self).bind_buffers()

    def execute(self):
        """
        Use memset driver functions to fill tensor with scalar
        """
        # TODO: remove neon dependency
        self.out.fill(self.value)


class SetItemKernel(GPUKernel):
    def __init__(self, transformer, op):
        super(SetItemKernel, self).__init__(transformer)

        self.tensor, self.value = (_ for _ in op.call_info())
        self.item = op.item

    def bind_buffers(self):
        if isinstance(self.tensor, TensorDescription):
            self.tensor = self.tensor.value.tensor
        if isinstance(self.value, TensorDescription):
            self.value = self.value.value.tensor

    def execute(self):
        # TODO: remove neon dependency
        self.tensor.__setitem__(self.item, self.value)


class UnsliceKernel(GPUKernel):
    def __init__(self, transformer, op):
        super(UnsliceKernel, self).__init__(transformer)

        self.out_sliced, self.x = (_ for _ in op.call_info())
        self.out = op.tensor_description()

    def bind_buffers(self):
        if isinstance(self.out_sliced, TensorDescription):
            self.out_sliced = self.out_sliced.value.tensor
        if isinstance(self.x, TensorDescription):
            self.x = self.x.value.tensor
        if isinstance(self.out, TensorDescription):
            self.out = self.out.value.tensor

    def execute(self):
        # TODO: remove neon dependency
        self.out.fill(0)
        self.out_sliced[:] = self.x