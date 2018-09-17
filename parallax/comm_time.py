import re
from scipy import optimize
import numpy as np

def parse_comm(comm_file_path):
  total_data = {}
  data = []
  tensor_comm_log = {}
  comp_times = {}
  with open(comm_file_path, 'r') as f:
    num_partitions = None
    for line in f:
      if line.startswith('P'):
        if tensor_comm_log:
          for key, value in tensor_comm_log.items():
            if key not in total_data:
              total_data[key] = []
            total_data[key].append(value[2] - value[1])
            data.append((key, num_partitions, value[0], value[2] - value[1], value[1], value[2], value[3]))
          tensor_comm_log.clear()
        num_partitions = int(line.split('P')[1])
      elif line.startswith('('):
        assert num_partitions
        comp_times[num_partitions] = []
        for comp_time in line.split('), '):
          split = comp_time.strip('(').strip(')\n').split(', ')
          comp_times[num_partitions].append((int(split[0]), int(split[1])))
      elif num_partitions:
          comm_log = line.strip().split(', ')
          match = re.match('(.*)_([0-9]+)', comm_log[0])
          if match: 
            tensor_name = match.groups()[0]
          else:
            tensor_name = comm_log[0]
          bytes = int(comm_log[1])
          start_time = int(comm_log[2])
          duration = int(comm_log[3])
          if tensor_name not in tensor_comm_log:
            tensor_comm_log[tensor_name] = (bytes, start_time, start_time + duration, comm_log[4])
          else:
            old_start_time = tensor_comm_log[tensor_name][1]
            old_end_time = tensor_comm_log[tensor_name][2]
            new_start_time = min(start_time, old_start_time)
            new_end_time = max(old_end_time, start_time+duration)
            new_bytes = tensor_comm_log[tensor_name][0] + bytes
            tensor_comm_log[tensor_name] = (new_bytes, new_start_time, new_end_time, tensor_comm_log[tensor_name][3])
  if tensor_comm_log:
    for key, value in tensor_comm_log.items():
      if key not in total_data:
        total_data[key] = []
      total_data[key].append(value[2] - value[1])
      data.append((key, num_partitions, value[0], value[2] - value[1], value[1], value[2], value[3])) 
    tensor_comm_log.clear()

  #for key, value in total_data.items():
    #print(key)
    #print(value)
  return comp_times, data   

def find_partitons(data):
  partitions = []
  data_size = []
  comm_time = []
  for d in data:
    partitions.append(d[1])
    data_size.append(d[2])
    comm_time.append(d[3])
  fitfunc = lambda p, n, d: p[0] * n + p[1] * d / n
  errfunc = lambda p, n, d, y :(fitfunc(p, n, d) - y)
  p0 = np.random.rand(2)
  p, success = optimize.leastsq(errfunc, p0, args=(np.array(partitions), np.array(data_size), np.array(comm_time)))
  
  min_partitions = np.min(partitions)
  max_partitions = np.max(partitions)

  min_comm_time = -1
  optimal_partitions = -1
  for i in range(min_partitions, max_partitions+1):
    total_comm_time = 0
    for d in data_size:
      estimated_time = fitfunc(p, i, d)
      #print('data size: %d, partitions: %d, estimated_comm_time: %d' % (d, i, estimated_time))
      total_comm_time += estimated_time

    if min_comm_time < 0 or total_comm_time < min_comm_time:
      min_comm_time = total_comm_time
      optimal_partitions = i

  print('optimal partitions: %d, estimated total comm time : %d' % (optimal_partitions, min_comm_time))

def remove_overlap(comp_times, data):
  new_data = []
  for d in data:
    partitions = d[1]
    comm_time = d[3]
    start = d[4]
    end = d[5]
    #print(partitions)
    for s,e in comp_times[partitions]:
      if end < s:
        break  
      elif start > e:
        continue
      else:
        # overlap
        overlap_s = max(start, s)
        overlap_e = min(end, e)
        #assert overlap_s != start or overlap_e != end
        comm_time -= overlap_e - overlap_s
    if comm_time > 0:
      new_data.append((d[0], d[1], d[2], comm_time, d[4], d[5], d[6]))
  return new_data
   
if __name__ == '__main__':
  comm_file_path = '/home/soojeong/partitions_exp/parsed_comm/nmt/M8/parsed_comm'

  # data is a list of (name, #partitons, data_size, comm_time, start, end, comm_type)
  comp_times, data = parse_comm(comm_file_path)
  #print(data)
  ps_time = 0
  mpi_time = 0
  for d in data:
    if d[-1] == 'PS':
      ps_time += d[3]
    else:
      mpi_time += d[3]
  print(ps_time)
  print(mpi_time)
  #new_data = remove_overlap(comp_times, data)
  #print(new_data)
  #find_partitons(data)

