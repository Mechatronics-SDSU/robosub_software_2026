import socket
import struct
import numpy as np

TCP_IP = '127.0.0.1'    # localhost
TCP_PORT = 5000
BUFFER_SIZE = 2048
SAMPLING_RATE = 1
SPEED = 1480 # speed in m/s of sound traveling under water

class Hydrophone:
    def __init__(self):
        self.server = (TCP_IP, TCP_PORT)
        self.pinger_x = -1
        self.pinger_y = -1
        self.pinger_z = -1
        self.sock = self.connectToSocket()
        self.buffer = bytearray(BUFFER_SIZE)

    def connectToSocket(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(self.server)
            return sock 
        except Exception as e:
            print("Failed to connect to socket:", e)
            return None 
             
    def compute_tdoa(self, signal1, signal2, sampling_rate=SAMPLING_RATE):
        cross_corr = cross_correlation(signal1, signal2)
        sample_lag = np.argmax(cross_corr) - len(signal1) + 1
        tdoa = sample_lag / sampling_rate # convert to seconds
        return tdoa
    
    def compute_distances(self, tdoa1, tdoa2):
        d1 = tdoa1 * SPEED
        d2 = tdoa2 * SPEED
        return d1, d2
    
    def locate_pinger(self, d1, d2):
        
        return
        
    def triangulate(self):
        return

    def find_angle(self):
        return

    def receive(self):
            data_format = struct.Struct('B' * BUFFER_SIZE)
            try:
                bytesRead = self.sock.recv(BUFFER_SIZE)
                adc_data = data_format.unpack(bytesRead)
                signal_array = np.array(adc_data)
                return signal_array
            except Exception as e:
                print("Error receiving Hydrophone data:",e)
                self.sock.close()
                self.sock = self.connectToSocket()
                self.run()

    def printData(self, hydro_data):
        print("angle:", hydro_data[0], "x:", hydro_data[1], "y:", hydro_data[2], "z:", hydro_data[3])
        # data = [angle, location_x, location_y, location_z]

    def run(self):
        if self.sock:
            while True:
                    signal = self.receive()


class HydrophoneArray:
    def __init__(self, spacing, speed=SPEED):
        """
        Initialize the hydrophone pair.

        Parameters:
            spacing (float): Distance between the two hydrophones.
            speed (float): Speed of sound in water (default ~1480 m/s).
        """
        self.speed = speed
        self.update_positions(spacing)

    def update_positions(self, spacing=2):
        """
        Update the positions of the hydrophones along the x-axis (y=z=0).

        Parameters:
            spacing (float): New spacing between hydrophones.
        """
        self.spacing = spacing
        self.h1 = np.array([-spacing / 2, 0, 0])
        self.h2 = np.array([spacing / 2, 0, 0])
        self.h3 = np.array([0, spacing / 2, 0])

    def compute_distances(self, pinger_pos):
        """
        Compute distances from a pinger to each hydrophone.

        Parameters:
            pinger_pos (ndarray): 3D position of the pinger.

        Returns:
            tuple: Distances to hydrophone 1 and 2.
        """
        d1 = np.linalg.norm(pinger_pos - self.h1)
        d2 = np.linalg.norm(pinger_pos - self.h2)
        return d1, d2

    def compute_delay_samples(self, d1, d2, fs):
        """
        Compute the delay (in samples and seconds) between signals at the two hydrophones.

        Parameters:
            d1, d2 (float): Distances from pinger to hydrophones.
            fs (float): Sampling frequency.

        Returns:
            tuple: (delay in samples, delay in seconds)
        """
        delay_sec = (d2 - d1) / self.speed
        return int(np.round(delay_sec * fs)), delay_sec
    
    
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



if __name__ == "__main__":
    hydro = Hydrophone()
    hydro.run()
    

