from sklearn.preprocessing import normalize
from model.util import load_model
import torch
import numpy as np
from backend.app.config import settings
class InferenceService:
    def __init__(self,device:str) -> None:
        self.backbone=settings.BACKBONE
        self.device=device
        self.model=load_model(settings.CHECKPOINT_PATH,device,settings.BACKBONE,use_se=True)
        self.input_shape=settings.INPUT_SHAPE
        
    def load_image_from_array(self,npy_array:np.ndarray)->torch.Tensor:    
        if npy_array.shape[0] >= self.input_shape[0]:
            result = npy_array[:self.input_shape[0], :]
        else:
            result = np.zeros(self.input_shape)
            result[:npy_array.shape[0], :npy_array.shape[1]] = npy_array
        image = torch.from_numpy(result).unsqueeze(0).unsqueeze(0)
        return image.float()
    
    def get_feature(self, image: torch.Tensor) -> np.ndarray:
        data = image.to(self.device)

        with torch.no_grad():
            output = self.model(data)
        output = output.cpu().detach().numpy()
        output = normalize(output).flatten()

        return output

    def get_embedding(self, mel_spec: np.ndarray) -> np.ndarray:
        image = self.load_image_from_array(mel_spec)
        embedding = self.get_feature(image)
        return embedding
    def process_audio_to_embedding(self, mel_spec: np.ndarray) -> tuple[np.ndarray, dict]:
        embedding = self.get_embedding(mel_spec)

        metadata = {
            "embedding_dim": len(embedding),
            "input_shape": self.input_shape,
            "model_backbone": self.backbone
        }

        return embedding, metadata