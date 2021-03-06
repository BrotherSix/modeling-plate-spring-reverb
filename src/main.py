from __future__ import division
from __future__ import print_function

import sys
import os

from sacred import Experiment
from Config import config_ingredient

import numpy as np
import math

ex = Experiment('model training', ingredients=[config_ingredient])

# constants:

kSR = 16000
kN_dft = 4096 #FFT size and hope size should be equal to winLength
kN_hop = 4096
kContext = 4

import Evaluate
import Models
from Layers import Generator, GeneratorContextSpec, preProcessingData
import Utils

    
# model_type should be 'model_1' or 'model_2'

@ex.automain
def main(cfg, model_type):
   
    model_config = cfg[model_type]
        
    if os.path.isdir(model_config['modelsPath']) == False:
        os.mkdir(model_config['modelsPath'])

    i = 0
    while os.path.exists(model_config['modelsPath']+'model_%s.pkl' % i):
        i += 1
    model_config['modelName'] = 'model_%s' % i

    Utils.dumpPickle(model_config, model_config['modelName']+ '.pkl', model_config['modelsPath'])
    
    try:

        # Xtrain, Ytrain, Xval, Yval should be tensors of shape (number_of_recordings, number_of_samples, 1) 
        Xtrain = np.random.rand(1, 2*kSR, 1)
        Ytrain = np.random.rand(1, 2*kSR, 1)
        Xval = np.random.rand(1, 2*kSR, 1)
        Yval = np.random.rand(1, 2*kSR, 1)
        
        # since the samples are 2 secs long, we zero pad 4*hop_size samples at the end of the recording. This for the 4 
        # subsequent frames in the Leslie modeling tasks.
        Xtrain = Utils.cropAndPad(Xtrain, crop = 0, pad = kContext*model_config['winLength']//2)
        Ytrain = Utils.cropAndPad(Ytrain, crop = 0, pad = kContext*model_config['winLength']//2)
        Xval = Utils.cropAndPad(Xval, crop = 0, pad = kContext*model_config['winLength']//2)
        Yval = Utils.cropAndPad(Yval, crop = 0, pad = kContext*model_config['winLength']//2)
        
        kLen = Xtrain.shape[1]
        kBatch = int((kLen/(model_config['winLength']//2)) + 1)
            
        YDtrain, _ = preProcessingData(Ytrain,  model_config['winLength'], model_config['winLength']//2,
                      window = True, preEmphasis = False,
                      spec = True, n_fft = kN_dft, n_hop = kN_hop, log = True, power = 2.0)
    
        Ytrain_w = preProcessingData(Ytrain,  model_config['winLength'], model_config['winLength']//2,
                          window = True, preEmphasis = False,
                          spec = False)



        YDval, _ = preProcessingData(Yval, model_config['winLength'], model_config['winLength']//2,
                          window = True, preEmphasis = False,
                          spec = True, n_fft = kN_dft, n_hop = kN_hop, log = True, power = 2.0)

        Yval_w = preProcessingData(Yval, model_config['winLength'], model_config['winLength']//2,
                          window = True, preEmphasis = False,
                          spec = False)


        if model_type in 'model_1':

            model = Models.model_1(model_config['winLength'],
                                model_config['filters'], 
                                model_config['kernelSize'], 
                                model_config['learningRate'], kBatch)

            trainGen = GeneratorContextSpec(Xtrain, [YDtrain, Ytrain_w], kContext,
                                        model_config['winLength'], model_config['winLength']//2,
                                        kN_dft, kN_hop, win = False, win_input=False)
            
            valGen = GeneratorContextSpec(Xval, [YDval, Yval_w], kContext,
                                        model_config['winLength'], model_config['winLength']//2,
                                        kN_dft, kN_hop, win = False, win_input=False)

        elif model_type in 'model_2':

            model = Models.model_2(model_config['winLength'],
                                model_config['filters'], 
                                model_config['kernelSize'], 
                                model_config['learningRate'])

            trainGen = GeneratorContextSpec(Xtrain, [YDtrain, Ytrain_w], kContext,
                                        model_config['winLength'], model_config['winLength']//2,
                                        kN_dft, kN_hop, win = False, win_input=False)
            
            valGen = GeneratorContextSpec(Xval, [YDval, Yval_w], kContext,
                                        model_config['winLength'], model_config['winLength']//2,
                                        kN_dft, kN_hop, win = False, win_input=False)

        

        print ('pretraining ', model_config['modelName'], 'type: ', model_type)
            
        earlyStopping_pre = Models.EarlyStopping(monitor='loss',
                                      min_delta=0,
                                      patience=25,
                                      verbose=1,
                                      mode='auto',
                                      baseline=None, restore_best_weights=False)

        checkpointer_pre = Models.ModelCheckpoint(filepath=model_config['modelsPath']+model_config['modelName']+'_chk.h5',
                                           monitor=model_config['monitorLoss'],
                                           verbose=1,
                                           save_best_only=True,
                                           save_weights_only=True)  

        model_pretraining = Models.pretrainingModel(model_config['winLength'],
                                model_config['filters'], 
                                model_config['kernelSize'], 
                                model_config['learningRate'])


        Xtrain_pre = np.vstack((Xtrain, Ytrain))
        Xval_pre = np.vstack((Xval, Yval))
        trainGen_pre = Generator(Xtrain_pre, Xtrain_pre, model_config['winLength'], model_config['winLength']//2)
        valGen_pre = Generator(Xval_pre, Xval_pre, model_config['winLength'], model_config['winLength']//2)   

        model_pretraining.fit_generator(trainGen_pre,
                       steps_per_epoch=None,
                       epochs=model_config['epoch'],
                       verbose=2,
                       callbacks = [checkpointer_pre, earlyStopping_pre],
                       validation_data = valGen_pre,
                       validation_steps=len(Xval),
                       shuffle=True)

        model.load_weights(model_config['modelsPath']+model_config['modelName']+'_chk.h5', by_name=True) 
        print ('Pretraining finished.')
                
        print('Training ', model_config['modelName'], 'type: ', model_type)
        
        model.summary()



        earlyStopping = Models.EarlyStopping(monitor=model_config['monitorLoss'],
                                          min_delta=0,
                                          patience=25,
                                          verbose=1,
                                          mode='auto',
                                          baseline=None, restore_best_weights=False)

        checkpointer = Models.ModelCheckpoint(filepath=model_config['modelsPath']+model_config['modelName']+'_chk.h5',
                                           monitor=model_config['monitorLoss'],
                                           verbose=1,
                                           save_best_only=True,
                                           save_weights_only=True)

        model.fit_generator(trainGen,
                           steps_per_epoch=None,
                           epochs=model_config['epoch'],
                           verbose=2,
                           callbacks = [checkpointer, earlyStopping],
                           validation_data = valGen,
                           validation_steps=len(Xval),
                           shuffle=True)

        print('Reducing Learning rate by 4')

        symbolic_weights = getattr(model.optimizer, 'weights')
        weight_values = Models.K.batch_get_value(symbolic_weights)

        model.compile(loss='mae',
                      optimizer=Models.Adam(lr=model_config['learningRate']/4))

        model.load_weights(model_config['modelsPath']+model_config['modelName']+'_chk.h5', by_name=True)

        model.fit_generator(trainGen,
                           steps_per_epoch=None,
                           epochs=model_config['epoch'],
                           verbose=2,
                           callbacks = [checkpointer, earlyStopping],
                           validation_data = valGen,
                           validation_steps=len(Xval),
                           shuffle=True)

        print('Training finished.')
        
        Evaluate.evaluate(cfg, model_type, model_config['modelName'])

    except Exception as e: 
        print(e)
        print('Training failed: ' + model_config['modelName'] + ' was removed')  
        os.remove(model_config['modelsPath']+model_config['modelName']+'.pkl')
    

    
    


   