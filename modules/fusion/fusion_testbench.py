import numpy as np 
import time
from algorithm import Fusion 


'''
FILE FOR TESTING SENSOR FUSION ALGORITHM.
'''


def main():
	

	test_2d = [2,4,6,8,10]
	test_2d_expected_x = [2,8,18,32,50]
	test_2d_measured_x = []
	test_accel = np.array([1.0, 0.0, 0.0])
	for test in test_2d:
		simulation = Fusion(True,test,test_accel)
		simulation.run_loop()
		x_measured = simulation.model_pos_space[0]
		test_2d_measured_x.append(x_measured)

	print("For 1 m/s^2 acceleration using 3 sensors in 2-D plane (constant euler angles (0,0,0), zero angular acceleration).\n")
	
	for i in range(len(test_2d)):

		abs_error = abs((test_2d_measured_x[i] - test_2d_expected_x[i]) / (test_2d_expected_x[i])) * 100.0
		print(f"Time tested: {test_2d[i]} seconds.")
		print(f"Expected: {test_2d_expected_x[i]:.2f}.\t Measured: {test_2d_measured_x[i]:.2f}.\t Error: {abs_error:.2f}.\n")






if __name__ == '__main__':
	main()