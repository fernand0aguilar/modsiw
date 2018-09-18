import numpy as np
from functools import partial
import PIL.Image
import tensorflow as tf
import matplotlib.pyplot as plt
import urllib.request
import os
import zipfile


def main():
    # Step 1 - Download google's pre-trained neural network
    url = 'https://storage.googleapis.com/download.tensorflow.org/models/inception5h.zip'
    data_dir = '../data/'
    model_name = os.path.split(url)[-1]
    local_zip_file = os.path.join(data_dir, model_name)

    if not os.path.exists(local_zip_file):
        # Download
        model_url = urllib.request.urlopen(url)
        with open(local_zip_file, 'wb') as output:
            output.write(model_url.read())

        #Extract
        with zipfile.ZipFile(local_zip_file, 'r') as zip_ref:
            zip_ref.extractall(data_dir)

    # Start with gray image and noise
    img_noise = np.random.uniform(size=(224, 224, 3)) + 100.0
    model_fn = 'tensorflow_inception_graph.pb'

    # Step 2 - Creating Tensorflow Session and Loading Model
    graph = tf.Graph()
    sess = tf.InteractiveSession(graph=graph)

    with tf.gfile.FastGFile(os.path.join(data_dir, model_fn), 'rb') as file:
        graph_def = tf.GraphDef()
        graph_def.ParseFromString(file.read())

    t_input = tf.placeholder(np.float32, name='input')  # define input tensor
    imagenet_mean = 117.0
    t_preprocessed = tf.expand_dims(t_input - imagenet_mean, 0)
    tf.import_graph_def(graph_def, {'input': t_preprocessed})

    layers = [
        op.name for op in graph.get_operations()
        if op.type == 'Conv2D' and 'import/' in op.name
    ]
    features_num = [
        int(graph.get_tensor_by_name(name + ':0').get_shape()[-1])
        for name in layers
    ]

    print('Number of layers ', len(layers))
    print('Total number of feature channels: ', sum(features_num))

    #End main

    # Helper functions for TF Graph visualization
    def strip_consts(graph_def, max_const_size=32):
        strip_def = tf.GraphDef()
        for n0 in graph_def.node:
            n = strip_def.node.add()  #pylint: disable=maybe-no-member
            n.MergeFrom(n0)
            if n.op == 'Const':
                tensor = n.attr['value'].tensor
                size = len(tensor.tensor_content)
                if size > max_const_size:
                    tensor.tensor_content = "<stripped %d bytes>" % size
            return strip_def

    #End strip_consts

    def rename_nodes(graph_def, rename_func):
        res_def = tf.GraphDef()
        for n0 in graph_def.node:
            n = res_def.node.add()
            n.MergeFrom(n0)
            n.name = rename_func(n.name)
            for i, s in enumerate(n.input):
                n.input[i] = rename_func(
                    s) if s[0] != '^' else '^' + rename_func(s[1:])
        return res_def

    #End rename_nodes

    def showarray(a):
        a = np.uint8(np.clip(a, 0, 1) * 255)
        plt.imshow(a)
        plt.show()

    #End showarray

    def visstd(a, s=0.1):
        return (a - a.mean()) / max(a.std(), 1e-4) * s + 0.5

    #End visstd

    def T(layer):
        return graph.get_tensor_by_name("import/%s:0" % layer)

    #End T

    def render_naive(t_obj, img0=img_noise, iter_n=20, step=1.0):
        t_score = tf.reduce_mean(t_obj)  # defining the optimization objective
        t_grad = tf.gradients(t_score, t_input)[0]

        img = img0.copy()
        for _ in range(iter_n):
            g, _ = sess.run([t_grad, t_score], {t_input: img})
            g /= g.std() + 1e-8
            img += g * step
        showarray(visstd(img))

    #End render_naive

    def tffunc(*argtypes):
        '''Helper that transforms TF-graph generating function into a regular one.
            See "resize" function below.
        '''
        placeholders = list(map(tf.placeholder, argtypes))

        def wrap(f):
            out = f(*placeholders)

            def wrapper(*args, **kw):
                return out.eval(
                    dict(zip(placeholders, args)), session=kw.get('session'))

            return wrapper

        return wrap

    def resize(img, size):
        img = tf.expand_dims(img, 0)
        return tf.image.resize_bilinear(img, size)[0, :, :, :]

    resize = tffunc(np.float32, np.int32)(resize)

    def calc_grad_tiled(img, t_grad, tile_size=512):
        '''Compute the value of tensor t_grad over the image in a tiled way.
        Random shifts are applied to the image to blur tile boundaries over 
        multiple iterations.'''
        sz = tile_size
        h, w = img.shape[:2]
        sx, sy = np.random.randint(sz, size=2)
        img_shift = np.roll(np.roll(img, sx, 1), sy, 0)
        grad = np.zeros_like(img)
        for y in range(0, max(h - sz // 2, sz), sz):
            for x in range(0, max(w - sz // 2, sz), sz):
                sub = img_shift[y:y + sz, x:x + sz]
                g = sess.run(t_grad, {t_input: sub})
                grad[y:y + sz, x:x + sz] = g
        return np.roll(np.roll(grad, -sx, 1), -sy, 0)


if __name__ == '__main__':
    main()