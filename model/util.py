import os

import torch

from model import ModelRegistry


def load_model(checkpoint_path:str,device:str,model_name:str,**kwargs):
    model=ModelRegistry.get(model_name,kwargs=kwargs)
    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(f"Checkpoint not found:{checkpoint_path}")
    state_dict = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()
    return model