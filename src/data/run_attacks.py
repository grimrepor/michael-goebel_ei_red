import os, sys
from glob import glob

import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from tqdm import tqdm

from advertorch.attacks import LinfPGDAttack, FGSM, JSMA
from advertorch.utils import NormalizeByChannelMeanStd

from torchvision.models import resnet50, vgg16
import torch, torch.nn as nn
from torch.utils.data import Dataset, DataLoader



assert len(sys.argv) == 2, 'Run with GPU ID as the second arg'

os.environ['CUDA_VISIBLE_DEVICES'] = sys.argv[1]
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


class MyDataLoader(Dataset):
    def __init__(self,paths):
        self.paths = paths

    def __len__(self): return len(self.paths)

    def __getitem__(self,i):
        label = int(self.paths[i].split('/')[-2][:4])
        img_pil = Image.open(self.paths[i]).convert('RGB').resize((256,256))
        img_torch = torch.tensor(np.array(img_pil,dtype=np.float32).transpose((2,0,1)))/255
        return img_torch, self.paths[i], label


data_dir = '../../data/'


tvt_fnames = list()


for t in ['train','val','test']:
    tvt_fnames.append(glob(data_dir + 'original_resized/' + t + '/*/*.png'))


tvt_maps = [MyDataLoader(l) for l in tvt_fnames]

tvt_loaders = [DataLoader(t,batch_size=32,shuffle=False) for t in tvt_maps]





normalize = NormalizeByChannelMeanStd(
    mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])

step_sizes = [1,2,3]
n_steps = [8,12,16]


base_models = [resnet50, vgg16]




#for b_model in [resnet50, vgg16]:
for b_model in [vgg16]:

    model = b_model(pretrained=True)
    model.eval()
    model = nn.Sequential(normalize, model).to(device)


    attacks = list()
    attack_names = list()


    for ss in step_sizes:
        attacks.append(FGSM(model,eps=ss/255.0))
        attack_names.append(f'{b_model.__name__}_FGSM_ss_{ss}')

        for ns in n_steps:
            attacks.append(LinfPGDAttack(model,eps=ss*ns/255.0, \
                    eps_iter=ss/255.0,nb_iter=ns))
            attack_names.append(f'{b_model.__name__}_PGD_ns_{ns}_ss_{ss}')

    for attack, attack_name in zip(attacks,attack_names):
        print(attack_name)
        for t_name, dg in zip(['train','val','test'],tvt_loaders):

            


    #for ns in n_steps:
    #    for ss in 



    attacks += [LinfPGDAttack(model,eps=ss*ns/255.0,eps_iter=ss/255.0,nb_iter=ns) for ss in step_sizes for ns in n_steps]
    attack_names += [f'{b_model.__name__}_PGD_ns_{ns}_ss_{ss}' for ss in step_sizes for ns in n_steps]

    attacks += [FGSM(model,eps=ss/255.0) for ss in step_sizes]
    attack_names += [f'{b_model.__name__}_FGSM_ss_{ss}' for ss in step_sizes]

    attacks = attacks[10:]
    attack_names = attack_names[10:]

    #print([(i,n) for i,n in enumerate(attack_names)])
    #quit()

    for attack,attack_name in zip(attacks,attack_names):
        print(attack_name)
        for t_name, dg in zip(['train','val','test'],tvt_loaders):

            for X, fnames, labels in tqdm(dg):
                adv_labels = (labels + torch.randint(1,1000,labels.shape)) % 1000
               
                f_tails = ['/'.join(os.path.splitext(f)[0].split('/')[-2:]) for f in fnames]

                X_adv = attack.perturb(X.to(device),adv_labels.to(device))

                for Xi, tail, new_label in zip(X_adv,f_tails,adv_labels):

                    X_np = (255*np.array(Xi.cpu()).transpose((1,2,0))).astype(np.uint8)


                    out_path = f'{data_dir}{attack_name}/{t_name}/{tail}_new_label_{new_label:04d}.png'
                    if not os.path.exists(os.path.dirname(out_path)):
                        os.makedirs(os.path.dirname(out_path))
                    Image.fromarray(X_np).save(out_path)



