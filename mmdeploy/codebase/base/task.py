# Copyright (c) OpenMMLab. All rights reserved.
import logging
from abc import ABCMeta, abstractmethod
from typing import Any, Dict, Optional, Sequence, Tuple, Union

import mmcv
import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

from mmdeploy.utils import get_codebase
from mmdeploy.utils.dataset import is_can_sort_dataset, sort_dataset


class BaseTask(metaclass=ABCMeta):
    """Wrap the processing functions of a Computer Vision task.

    Args:
        model_cfg (str | mmcv.Config): Model config file.
        deploy_cfg (str | mmcv.Config): Deployment config file.
        device (str): A string specifying device type.
    """

    def __init__(self, model_cfg: mmcv.Config, deploy_cfg: mmcv.Config,
                 device: str):

        self.model_cfg = model_cfg
        self.deploy_cfg = deploy_cfg
        self.device = device

        codebase = get_codebase(deploy_cfg)

        from .mmcodebase import get_codebase_class
        self.codebase_class = get_codebase_class(codebase)

    @abstractmethod
    def init_backend_model(self,
                           model_files: Sequence[str] = None,
                           **kwargs) -> torch.nn.Module:
        """Initialize backend model.

        Args:
            model_files (Sequence[str]): Input model files.

        Returns:
            nn.Module: An initialized backend model.
        """
        pass

    @abstractmethod
    def init_pytorch_model(self,
                           model_checkpoint: Optional[str] = None,
                           cfg_options: Optional[Dict] = None,
                           **kwargs) -> torch.nn.Module:
        """Initialize torch model.

        Args:
            model_checkpoint (str): The checkpoint file of torch model,
                defaults to `None`.
            cfg_options (dict): Optional config key-pair parameters.

        Returns:
            nn.Module: An initialized torch model generated by other OpenMMLab
                codebases.
        """
        pass

    def build_dataset(self,
                      dataset_cfg: Union[str, mmcv.Config],
                      dataset_type: str = 'val',
                      is_sort_dataset: bool = True,
                      **kwargs) -> Dataset:
        """Build dataset for different codebase.

        Args:
            dataset_cfg (str | mmcv.Config): Dataset config file or Config
                object.
            dataset_type (str): Specifying dataset type, e.g.: 'train', 'test',
                'val', defaults to 'val'.
            is_sort_dataset (bool): When 'True', the dataset will be sorted
                by image shape in ascending order if 'dataset_cfg'
                contains information about height and width.

        Returns:
            Dataset: The built dataset.
        """
        dataset = self.codebase_class.build_dataset(dataset_cfg, dataset_type,
                                                    **kwargs)
        if is_sort_dataset:
            if is_can_sort_dataset(dataset):
                sort_dataset(dataset)
            else:
                logging.info('Sorting the dataset by \'height\' and \'width\' '
                             'is not possible.')
        return dataset

    def build_dataloader(self, dataset: Dataset, samples_per_gpu: int,
                         workers_per_gpu: int, **kwargs) -> DataLoader:
        """Build PyTorch dataloader.

        Args:
            dataset (Dataset): A PyTorch dataset.
            samples_per_gpu (int): Number of training samples on each GPU,
                i.e., batch size of each GPU.
            workers_per_gpu (int): How many subprocesses to use for data
                loading for each GPU.

        Returns:
            DataLoader: A PyTorch dataloader.
        """
        return self.codebase_class.build_dataloader(dataset, samples_per_gpu,
                                                    workers_per_gpu, **kwargs)

    def single_gpu_test(self,
                        model: torch.nn.Module,
                        data_loader: DataLoader,
                        show: bool = False,
                        out_dir: Optional[str] = None,
                        **kwargs):
        """Run test with single gpu.

        Args:
            model (torch.nn.Module): Input model from nn.Module.
            data_loader (DataLoader): PyTorch data loader.
            show (bool): Specifying whether to show plotted results. Defaults
                to `False`.
            out_dir (str): A directory to save results, defaults to `None`.

        Returns:
            list: The prediction results.
        """
        return self.codebase_class.single_gpu_test(model, data_loader, show,
                                                   out_dir, **kwargs)

    @abstractmethod
    def create_input(self,
                     imgs: Union[str, np.ndarray],
                     input_shape: Sequence[int] = None,
                     **kwargs) -> Tuple[Dict, torch.Tensor]:
        """Create input for model.

        Args:
            imgs (str | np.ndarray): Input image(s), accpeted data types are
                `str`, `np.ndarray`.
            input_shape (list[int]): Input shape of image in (width, height)
                format, defaults to `None`.

        Returns:
            tuple: (data, img), meta information for the input image and input
                image tensor.
        """
        pass

    @abstractmethod
    def visualize(self,
                  model: torch.nn.Module,
                  image: Union[str, np.ndarray],
                  result: list,
                  output_file: str,
                  window_name: str = '',
                  show_result: bool = False,
                  **kwargs):
        """Visualize predictions of a model.

        Args:
            model (nn.Module): Input model.
            image (str | np.ndarray): Input image to draw predictions on.
            result (list): A list of predictions.
            output_file (str): Output file to save drawn image.
            backend (Backend): Specifying backend type.
            window_name (str): The name of visualization window. Defaults to
                an empty string.
            show_result (bool): Whether to show result in windows, defaults
                to `False`.
        """
        pass

    @staticmethod
    @abstractmethod
    def run_inference(model, model_inputs: Dict[str, torch.Tensor]):
        """Run inference once for a model of a OpenMMLab Codebase.

        Args:
            model (nn.Module): Input model.
            model_inputs (dict): A dict containing model inputs tensor and
                meta info.

        Returns:
            list: The predictions of model inference.
        """
        pass

    @staticmethod
    @abstractmethod
    def get_partition_cfg(partition_type: str, **kwargs) -> Dict:
        """Get a certain partition config.

        Args:
            partition_type (str): A string specifying partition type.

        Returns:
            dict: A dictionary of partition config.
        """
        pass

    @staticmethod
    @abstractmethod
    def get_tensor_from_input(self, input_data: Dict[str, Any],
                              **kwargs) -> torch.Tensor:
        """Get input tensor from input data.

        Args:
            input_data (dict): Input data containing meta info and image
                tensor.
        Returns:
            torch.Tensor: An image in `Tensor`.
        """
        pass

    @staticmethod
    @abstractmethod
    def evaluate_outputs(model_cfg,
                         outputs: Sequence,
                         dataset: Dataset,
                         metrics: Optional[str] = None,
                         out: Optional[str] = None,
                         metric_options: Optional[dict] = None,
                         format_only: bool = False,
                         **kwargs):
        """Perform post-processing to predictions of model.

        Args:
            outputs (list): A list of predictions of model inference.
            dataset (Dataset): Input dataset to run test.
            model_cfg (mmcv.Config): The model config.
            codebase (Codebase): Specifying codebase type.
            metrics (str): Evaluation metrics, which depends on
                the codebase and the dataset, e.g., "bbox", "segm", "proposal"
                for COCO, and "mAP", "recall" for PASCAL VOC in mmdet;
                "accuracy", "precision", "recall", "f1_score", "support"
                for single label dataset, and "mAP", "CP", "CR", "CF1",
                "OP", "OR", "OF1" for multi-label dataset in mmcls.
                Defaults is `None`.
            out (str): Output result file in pickle format, defaults to `None`.
            metric_options (dict): Custom options for evaluation, will be
                kwargs for dataset.evaluate() function. Defaults to `None`.
            format_only (bool): Format the output results without perform
                evaluation. It is useful when you want to format the result
                to a specific format and submit it to the test server. Defaults
                to `False`.
        """
        pass
