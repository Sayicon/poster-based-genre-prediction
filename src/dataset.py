from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from torch.utils.data import Dataset


class PosterDataset(Dataset):
    def __init__(self, csv_path, posters_dir, mlb, transform=None):
        self.df = pd.read_csv(csv_path)
        self.posters_dir = Path(posters_dir)
        self.transform = transform

        genre_lists = self.df["genres"].str.split("|").tolist()
        self.labels = mlb.transform(genre_lists).astype(np.float32)

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        img = np.array(Image.open(self.posters_dir / f"{row['tmdb_id']}.jpg").convert("RGB"))

        if self.transform:
            img = self.transform(image=img)["image"]

        return img, self.labels[idx]
