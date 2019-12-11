from sacred import Ingredient

config_ingredient = Ingredient("cfg")

@config_ingredient.config
def cfg():
    
    # models configuration
    
    pretraining = { 'epoch' : 1,
                    'filters' : 32,
                    'kernelSize' : 64,
                    'learningRate' : 0.0001,
                    'winLength' : 4096,
                    'modelsPath': './Models/',
                    'monitorLoss': 'val_loss'
                   }
    
    model_1 = { 'epoch' : 1,
                    'filters' : 32,
                    'kernelSize' : 64,
                    'learningRate' : 0.0001,
                    'winLength' : 4096,
                    'modelsPath': './Models/',
                    'monitorLoss': 'val_loss'
                   }
    
    
    model_2 = { 'epoch' : 1,
                    'filters' : 32,
                    'kernelSize' : 64,
                    'learningRate' : 0.0001,
                    'winLength' : 4096,
                    'modelsPath': './Models/',
                    'monitorLoss': 'val_loss'
                   }
    
    

    