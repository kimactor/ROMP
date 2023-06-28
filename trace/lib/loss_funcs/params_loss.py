from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import torch
import torch.nn as nn
import sys, os
root_dir = os.path.join(os.path.dirname(__file__),'..')
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import time
import pickle
import numpy as np

import config
import constants
from config import args
from utils import batch_rodrigues, rotation_matrix_to_angle_axis

def batch_l2_loss(real,predict):
    if len(real) == 0:
        return 0
    loss = torch.norm(real-predict, p=2, dim=1)
    loss = loss[~torch.isnan(loss)]
    if len(loss) == 0:
        return 0
    return loss#.mean()

def batch_smpl_pose_l2_error(real,predict):
    # convert to rot mat, multiple angular maps to the same rotation with Pi as a period.
    batch_size = real.shape[0]
    real = batch_rodrigues(real.reshape(-1,3)).contiguous()#(N*J)*3 -> (N*J)*3*3
    predict = batch_rodrigues(predict.reshape(-1,3)).contiguous()#(N*J)*3 -> (N*J)*3*3
    loss = torch.norm((real-predict).view(-1,9), p=2, dim=-1)#self.sl1loss(real,predict)#
    loss = loss.reshape(batch_size, -1).mean(-1)
    return loss

def trans_relative_rot_to_global_rotmat(params, with_global_rot=False):
    '''
    calculate absolute rotation matrix in the global coordinate frame of K body parts. 
    The rotation is the map from the local bone coordinate frame to the global one.
    K= 9 parts in the following order: 
    root (JOINT 0) , left hip  (JOINT 1), right hip (JOINT 2), left knee (JOINT 4), right knee (JOINT 5), 
    left shoulder (JOINT 16), right shoulder (JOINT 17), left elbow (JOINT 18), right elbow (JOINT 19).
    parent kinetic tree [-1,  0,  0,  0,  1,  2,  3,  4,  5,  6,  7,  8,  9,  9,  9, 12, 13, 14, 16, 17, 18, 19, 20, 21]
    '''
    batch_size, param_num = params.shape[0], params.shape[1]//3
    pose_rotmat = batch_rodrigues(params.reshape(-1,3)).view(batch_size, param_num, 3, 3).contiguous()
    if with_global_rot:
        sellect_joints = np.array([0,1,2,4,5,16,17,18,19],dtype=np.int32)
        results = [pose_rotmat[:, 0]]
        for idx in range(param_num-1):
            i_val = int(idx + 1)
            joint_rot = pose_rotmat[:, i_val]
            parent = constants.kintree_parents[i_val]
            glob_transf_mat = torch.matmul(results[parent], joint_rot)
            results.append(glob_transf_mat)
    else:
        sellect_joints = np.array([1,2,4,5,16,17,18,19],dtype=np.int32)-1
        results = [torch.eye(3,3)[None].cuda().repeat(batch_size,1,1)]
        for i_val in range(param_num-1):
            #i_val = int(idx + 1)
            joint_rot = pose_rotmat[:, i_val]
            parent = constants.kintree_parents[i_val+1]
            glob_transf_mat = torch.matmul(results[parent], joint_rot)
            results.append(glob_transf_mat)
    global_rotmat = torch.stack(results, axis=1)[:, sellect_joints].contiguous()
    return global_rotmat
