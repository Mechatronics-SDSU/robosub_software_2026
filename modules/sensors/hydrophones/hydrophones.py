import socket
import struct
import numpy as np
from scipy.optimize import least_squares

def cross_correlation(x, y):
    """
    Compute the unnormalized cross-correlation of two signals using FFT.

    The cross-correlation is computed by:
      - Taking the FFT of both signals.
      - Multiplying one FFT by the complex conjugate of the other.
      - Taking the inverse FFT of the product.
      - Applying FFT shift to center the zero lag.

    Parameters:
        x, y (array_like): Input signals (of the same length).

    Returns:
        ndarray: The cross-correlation of x and y.
    """
    X = np.fft.fft(x)
    Y = np.fft.fft(y)
    corr = np.fft.ifft(X * np.conjugate(Y))
    return np.fft.fftshift(corr)

TCP_IP = '127.0.0.1'
TCP_PORT = 5000
BUFFER_SIZE = 4                 # 4 bytes: 1st = error code, 2nd/3rd = time difference, 4th = end of message (0x0D new line)
SAMPLING_RATE = 2 * 40000       # Nyquist rate = 2 * highest frequency
SPEED = 1480                    # speed in m/s of sound traveling under water

class Hydrophone:
    def __init__(self):
        self.server = (TCP_IP, TCP_PORT)
        self.sock = self.connectToSocket()
        self.buffer = bytearray(BUFFER_SIZE)
        self.hydro1 = np.array([0.0, 0.0, 0.0])
        self.hydro2 = np.array([10.0, 0.0, 0.0])
        self.hydro3 = np.array([3.0, 4.0, 0.0])

    def connectToSocket(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(self.server)
            print("Connected to socket")
            return sock 
        except Exception as e:
            print("Failed to connect to socket:", e)
            return None 
             
    def compute_tdoa(self, signal1, signal2, sampling_rate=SAMPLING_RATE):
        cross_corr = cross_correlation(signal1, signal2)
        sample_lag = np.argmax(cross_corr) - len(signal1) + 1
        tdoa = sample_lag / sampling_rate # convert to seconds
        return tdoa
    
    def compute_distances(self, sig1, sig2, sig3):
        tdoa12 = self.compute_tdoa(sig1, sig2)
        tdoa13 = self.compute_tdoa(sig1, sig3)

        d1 = tdoa12 * SPEED
        d2 = tdoa13 * SPEED

        return d1, d2
    
    def locate_pinger(self, signal1, signal2, signal3):
        

        return
        
    def trilaterate(self):

        return

    def find_angle(self): 
        return

    def receive(self):
            data_format = struct.Struct('B' * BUFFER_SIZE)
            try:
                bytesRead = self.sock.recv(BUFFER_SIZE)
                adc_data = data_format.unpack(bytesRead)
                signal_array = np.array(adc_data)
                print(signal_array)
                return signal_array
            except Exception as e:
                print("Error receiving Hydrophone data:",e)
                self.sock.close()
                self.sock = self.connectToSocket()
                self.run()

    def send(self):
        return
    
    def printData(self, hydro_data):
        print("angle:", hydro_data[0], "x:", hydro_data[1], "y:", hydro_data[2], "z:", hydro_data[3])
        # data = [angle, location_x, location_y, location_z]

    def run(self):
        if self.sock:
            while True:
                    signal1 = self.receive()
                    signal2 = self.receive()
                    signal3 = self.receive()
                    if(signal1 and signal2 and signal3):
                        self.locate_pinger(signal1, signal2, signal3)


if __name__ == "__main__":
    hydro = Hydrophone()
    hydro.run()
    

