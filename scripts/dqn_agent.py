# scripts/dqn_agent.py
import numpy as np
import random
from collections import deque
import tensorflow as tf
from tensorflow.keras import Sequential
from tensorflow.keras.layers import Dense
from tensorflow.keras.optimizers import Adam
import joblib
import os

class DQNAgent:
    """
    Deep Q-Network Agent untuk orkestrasi multi-agent.
    State: regime (one-hot) + indikator teknikal + performa agent.
    Action: pilih agent (0-3) atau weighted voting (4)
    """
    
    def __init__(self, state_size, action_size, learning_rate=0.001, gamma=0.95, 
                 epsilon=1.0, epsilon_min=0.01, epsilon_decay=0.995, 
                 memory_size=2000, batch_size=32, target_update=100):
        
        self.state_size = state_size
        self.action_size = action_size
        self.lr = learning_rate
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay
        self.batch_size = batch_size
        self.target_update = target_update
        self.train_step = 0
        
        # Replay memory
        self.memory = deque(maxlen=memory_size)
        
        # Main network dan target network
        self.model = self._build_model()
        self.target_model = self._build_model()
        self.update_target_model()
        
        self.model_path = 'data/dqn_agent.h5'
        if os.path.exists(self.model_path):
            self.load()
    
    def _build_model(self):
        """Bangun neural network dengan 3 hidden layer."""
        model = Sequential([
            Dense(128, activation='relu', input_dim=self.state_size),
            Dense(128, activation='relu'),
            Dense(64, activation='relu'),
            Dense(self.action_size, activation='linear')
        ])
        model.compile(loss='mse', optimizer=Adam(learning_rate=self.lr))
        return model
    
    def update_target_model(self):
        """Copy weights dari main network ke target network."""
        self.target_model.set_weights(self.model.get_weights())
    
    def remember(self, state, action, reward, next_state, done):
        """Simpan experience ke memory."""
        self.memory.append((state, action, reward, next_state, done))
    
    def act(self, state, use_epsilon=True):
        """Pilih aksi berdasarkan state."""
        if use_epsilon and np.random.rand() <= self.epsilon:
            return random.randrange(self.action_size)
        q_values = self.model.predict(state, verbose=0)
        return np.argmax(q_values[0])
    
    def replay(self):
        """Training dengan random sample dari memory."""
        if len(self.memory) < self.batch_size:
            return
        
        minibatch = random.sample(self.memory, self.batch_size)
        
        states = np.array([t[0] for t in minibatch]).reshape(-1, self.state_size)
        actions = np.array([t[1] for t in minibatch])
        rewards = np.array([t[2] for t in minibatch])
        next_states = np.array([t[3] for t in minibatch]).reshape(-1, self.state_size)
        dones = np.array([t[4] for t in minibatch])
        
        # Q values saat ini
        targets = self.model.predict(states, verbose=0)
        
        # Q values berikutnya dari target network
        next_q = self.target_model.predict(next_states, verbose=0)
        max_next_q = np.max(next_q, axis=1)
        
        for i in range(self.batch_size):
            if dones[i]:
                targets[i, actions[i]] = rewards[i]
            else:
                targets[i, actions[i]] = rewards[i] + self.gamma * max_next_q[i]
        
        # Training
        self.model.fit(states, targets, epochs=1, verbose=0, batch_size=self.batch_size)
        
        # Update target network periodically
        self.train_step += 1
        if self.train_step % self.target_update == 0:
            self.update_target_model()
        
        # Decay epsilon
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
    
    def save(self):
        self.model.save(self.model_path)
    
    def load(self):
        self.model = tf.keras.models.load_model(self.model_path)
        self.update_target_model()
    
    def get_q_table(self):
        """Untuk debugging, kembalikan Q-values untuk state tertentu."""
        pass