import tensorflow as tf
import numpy as np
import os
import json


class PredictionType:
    CLASSIFICATION = 'CLASSIFICATION'
    REGRESSION = 'REGRESSION'


class Params:
    def __init__(self, **kwargs):
        self._n_epochs = kwargs.get('n_epochs', 20)
        self._evaluate_every_epoch = kwargs.get('evaluate_every_epochs', 5)
        self._learning_rate = kwargs.get('learning_rate', 1e-5)
        self._exponential_learning = kwargs.get('exponential_learning', True)
        self._batch_size = kwargs.get('batch_size', 5)
        self._batch_norm = kwargs.get('batch_norm', False)
        self._weight_decay = kwargs.get('weight_decay', 1e-5)
        self._data_augmentation = kwargs.get('data_augmentation', True)
        self._make_patches = kwargs.get('make_patches', False)
        self._patch_shape = kwargs.get('patch_shape', (300, 300))
        self._input_resized_size = kwargs.get('resized_size', (480, 320))
        self._input_dir_train = kwargs.get('input_dir_train')
        self._input_dir_eval = kwargs.get('input_dir_eval')
        self._output_model_dir = kwargs.get('output_model_dir')
        self._gpu = kwargs.get('gpu', '')
        self._class_file = kwargs.get('class_file')
        self._pretrained_model_name = kwargs.get('model_name')
        # self._pretrained_model_file = kwargs.get('pretrained_file')
        self._prediction_type = self._set_prediction_type(kwargs.get('prediction_type'))
        self._vgg_intermediate_conv = kwargs.get('vgg_intermediate_conv')
        self._vgg_upscale_params = kwargs.get('vgg_upscale_params')
        self._vgg_selected_levels_upscaling = kwargs.get('vgg_selected_levels_upscaling')

        # Prediction type check
        if self._prediction_type == PredictionType.CLASSIFICATION:
            assert self.class_file is not None
        elif self._prediction_type == PredictionType.REGRESSION:
            self._n_classes = 1

        # Pretrained model name check
        if self._pretrained_model_name == 'vgg16':
            assert self._vgg_upscale_params is not None and self._vgg_selected_levels_upscaling is not None, \
                'VGG16 parameters cannot be None'

            assert len(self._vgg_upscale_params) == len(self._vgg_selected_levels_upscaling), \
                'Upscaling levels and selection levels must have the same lengths (in model_params definition), ' \
                '{} != {}'.format(len(self._vgg_upscale_params),
                                  len(self._vgg_selected_levels_upscaling))

            self._pretrained_model_file = '/mnt/cluster-nas/benoit/pretrained_nets/vgg_16.ckpt'
        else:
            raise NotImplementedError

    def _set_prediction_type(self, prediction_type):
            if prediction_type == 'CLASSIFICATION':
                return PredictionType.CLASSIFICATION
            elif prediction_type == 'REGRESSION':
                return PredictionType.REGRESSION
            else:
                raise NotImplementedError

    def export_experiment_params(self):
        if not os.path.isdir(self.output_model_dir):
            os.mkdir(self.output_model_dir)
        with open(os.path.join(self.output_model_dir, 'model_params.json'), 'w') as f:
            json.dump(vars(self), f)

    @property
    def output_model_dir(self):
        return self._output_model_dir

    @property
    def input_dir_train(self):
        return self._input_dir_train

    @property
    def input_dir_eval(self):
        return self._input_dir_eval

    @property
    def class_file(self):
        return self._class_file

    @property
    def prediction_type(self):
        return self._prediction_type

    @property
    def gpu(self):
        return self._gpu

    @property
    def n_classes(self):
        return self._n_classes

    @n_classes.setter
    def n_classes(self, value):
        self._n_classes = value

    @property
    def input_resized_size(self):
        return self._input_resized_size

    @property
    def evaluate_every_epoch(self):
        return self._evaluate_every_epoch

    @property
    def n_epochs(self):
        return self._n_epochs

    @property
    def batch_size(self):
        return self._batch_size

    @property
    def batch_norm(self):
        return self._batch_norm

    @property
    def data_augmentation(self):
        return self._data_augmentation

    @property
    def make_patches(self):
        return self._make_patches

    @property
    def patch_shape(self):
        return self._patch_shape

    @property
    def weight_decay(self):
        return self._weight_decay

    @property
    def learning_rate(self):
        return self._learning_rate

    @property
    def exponential_learning(self):
        return self._exponential_learning

    @property
    def vgg_intermediate_conv(self):
        return self._vgg_intermediate_conv

    @property
    def vgg_upscale_params(self):
        return self._vgg_upscale_params

    @property
    def vgg_selected_levels_upscaling(self):
        return self._vgg_selected_levels_upscaling

    @property
    def pretrained_model_file(self):
        return self._pretrained_model_file

    @property
    def pretrained_model_name(self):
        return self._pretrained_model_name


def label_image_to_class(label_image: tf.Tensor, classes_file: str) -> tf.Tensor:
    classes_color_values = get_classes_color_from_file(classes_file)
    # Convert label_image [H,W,3] to the classes [H,W],int32 according to the classes [C,3]
    with tf.name_scope('LabelAssign'):
        if len(label_image.get_shape()) == 3:
            diff = tf.cast(label_image[:, :, None, :], tf.float32) - tf.constant(classes_color_values[None, None, :, :])  # [H,W,C,3]
        elif len(label_image.get_shape()) == 4:
            diff = tf.cast(label_image[:, :, :, None, :], tf.float32) - tf.constant(
                classes_color_values[None, None, None, :, :])  # [B,H,W,C,3]
        else:
            raise NotImplementedError

        pixel_class_diff = tf.reduce_sum(tf.square(diff), axis=-1)  # [H,W,C] or [B,H,W,C]
        class_label = tf.argmin(pixel_class_diff, axis=-1)  # [H,W] or [B,H,W]
        return class_label


def class_to_label_image(class_label: tf.Tensor, classes_file: str) -> tf.Tensor:
    classes_color_values = get_classes_color_from_file(classes_file)
    return tf.gather(classes_color_values, tf.cast(class_label, dtype=tf.int32))


def get_classes_color_from_file(classes_file: str) -> np.ndarray:
    if not os.path.exists(classes_file):
        raise FileNotFoundError(classes_file)
    result = np.loadtxt(classes_file).astype(np.float32)
    assert result.shape[1] == 3, "Color file should represent RGB values"
    return result