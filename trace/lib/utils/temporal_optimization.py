
import numpy as np
from .util import transform_rot_representation

def extract_motion_sequence(results_track_video, video_track_ids):
    motion_sequence = {}
    frame_ids = sorted(list(results_track_video.keys()))
    subject_ids = []
    for fid, track_ids in video_track_ids.items():
        subject_ids.extend(track_ids)
    subject_ids = np.unique(np.array(subject_ids))
    for subject_id in subject_ids:
        frame_ids_appear = {fid:np.where(np.array(track_ids)==subject_id)[0][0] for fid, track_ids in video_track_ids.items() if subject_id in track_ids}
        motion_sequence[subject_id] = [results_track_video[frame_ids[fid]][sid] for fid, sid in frame_ids_appear.items()]
        
    return motion_sequence

def creat_OneEuroFilter():
  return {'cam': OneEuroFilter(4.0, 0.0), 'global_orient': OneEuroFilter(4.0, 0.0), 'pose': OneEuroFilter(4.0, 0.0), 'smpl_betas': OneEuroFilter(4.0, 0.0)} 


def temproal_optimize_result(result, filter_dict):
  result['cam'] = filter_dict['cam'].process(result['cam'])
  result['smpl_betas'] = filter_dict['smpl_betas'].process(result['smpl_betas'])
  pose_euler = np.array([transform_rot_representation(vec, input_type='vec',out_type='euler') for vec in result['pose'].reshape((-1,3))])
  #global_orient_euler = filter_dict['global_orient'].process(pose_euler[:1])
  #result['pose'][:3] = transform_rot_representation(global_orient_euler, input_type='euler',out_type='vec')
  body_pose_euler = filter_dict['pose'].process(pose_euler[1:].reshape(-1))
  result['pose'][3:] = np.array([transform_rot_representation(bodypose, input_type='euler',out_type='vec') for bodypose in body_pose_euler.reshape(-1,3)]).reshape(-1)
  return result

def optimize_temporal_smoothness(motion_sequences):
  subject_ids = list(motion_sequences.keys())
  for subject_id in subject_ids:
    mot_seq = motion_sequences[subject_id]
    mot_num = len(mot_seq)
    filter_dict = creat_OneEuroFilter()
    for mid in range(mot_num):
      mot_seq[mid]['cam'] = filter_dict['cam'].process(mot_seq[mid]['cam'])
      mot_seq[mid]['smpl_betas'] = filter_dict['smpl_betas'].process(mot_seq[mid]['smpl_betas'])
      pose_euler = np.array([transform_rot_representation(vec, input_type='vec',out_type='euler') for vec in mot_seq[mid]['pose'].reshape((-1,3))])
      #global_orient_euler = filter_dict['global_orient'].process(pose_euler[:1])
      #mot_seq[mid]['pose'][:3] = transform_rot_representation(global_orient_euler, input_type='euler',out_type='vec')
      body_pose_euler = filter_dict['pose'].process(pose_euler[1:].reshape(-1))
      mot_seq[mid]['pose'][3:] = np.array([transform_rot_representation(bodypose, input_type='euler',out_type='vec') for bodypose in body_pose_euler.reshape(-1,3)]).reshape(-1)
  return motion_sequences

'''
learn from the minimal hand https://github.com/CalciferZh/minimal-hand
'''
class LowPassFilter:
  def __init__(self):
    self.prev_raw_value = None
    self.prev_filtered_value = None

  def process(self, value, alpha):
    if self.prev_raw_value is None:
      s = value
    else:
      s = alpha * value + (1.0 - alpha) * self.prev_filtered_value
    self.prev_raw_value = value
    self.prev_filtered_value = s
    return s

class OneEuroFilter:
  def __init__(self, mincutoff=1.0, beta=0.0, dcutoff=1.0, freq=30):
    self.freq = freq
    self.mincutoff = mincutoff
    self.beta = beta
    self.dcutoff = dcutoff
    self.x_filter = LowPassFilter()
    self.dx_filter = LowPassFilter()

  def compute_alpha(self, cutoff):
    te = 1.0 / self.freq
    tau = 1.0 / (2 * np.pi * cutoff)
    return 1.0 / (1.0 + tau / te)

  def process(self, x):
    prev_x = self.x_filter.prev_raw_value
    dx = 0.0 if prev_x is None else (x - prev_x) * self.freq
    edx = self.dx_filter.process(dx, self.compute_alpha(self.dcutoff))
    cutoff = self.mincutoff + self.beta * np.abs(edx)
    return self.x_filter.process(x, self.compute_alpha(cutoff))