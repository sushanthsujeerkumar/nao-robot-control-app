import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';
import axios from 'axios';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL + '/api';

// Types
export interface RobotConfig {
  id: string;
  name: string;
  ip_address: string;
  port: number;
  created_at: string;
  last_connected?: string;
}

export interface RobotStatus {
  connected: boolean;
  ip_address: string | null;
  battery_level: number;
  temperature: number;
  robot_name: string;
  uptime: number;
  posture: string;
}

export interface SensorData {
  head_touch_front: boolean;
  head_touch_middle: boolean;
  head_touch_rear: boolean;
  left_hand_touch: boolean;
  right_hand_touch: boolean;
  sonar_left: number;
  sonar_right: number;
  battery_level: number;
  head_yaw: number;
  head_pitch: number;
  left_shoulder_pitch: number;
  right_shoulder_pitch: number;
  temperature_cpu: number;
  temperature_battery: number;
  timestamp: string;
}

export interface Gesture {
  name: string;
  description: string;
  icon: string;
}

interface RobotStore {
  // State
  savedRobots: RobotConfig[];
  currentRobot: RobotConfig | null;
  status: RobotStatus | null;
  sensors: SensorData | null;
  gestures: Gesture[];
  isConnecting: boolean;
  isLoading: boolean;
  error: string | null;
  
  // Actions
  fetchSavedRobots: () => Promise<void>;
  saveRobot: (name: string, ip: string, port: number) => Promise<void>;
  deleteRobot: (id: string) => Promise<void>;
  connectToRobot: (ip: string, port: number) => Promise<boolean>;
  disconnectFromRobot: () => Promise<void>;
  fetchStatus: () => Promise<void>;
  fetchSensors: () => Promise<void>;
  fetchGestures: () => Promise<void>;
  sendMoveCommand: (x: number, y: number, theta: number) => Promise<void>;
  stopMovement: () => Promise<void>;
  speak: (text: string) => Promise<void>;
  executeGesture: (gestureName: string) => Promise<void>;
  setCurrentRobot: (robot: RobotConfig | null) => void;
  clearError: () => void;
}

export const useRobotStore = create<RobotStore>((set, get) => ({
  savedRobots: [],
  currentRobot: null,
  status: null,
  sensors: null,
  gestures: [],
  isConnecting: false,
  isLoading: false,
  error: null,

  fetchSavedRobots: async () => {
    set({ isLoading: true, error: null });
    try {
      const response = await axios.get(`${API_URL}/robots`);
      set({ savedRobots: response.data, isLoading: false });
    } catch (error: any) {
      console.error('Error fetching robots:', error);
      set({ error: error.message, isLoading: false });
    }
  },

  saveRobot: async (name: string, ip: string, port: number) => {
    set({ isLoading: true, error: null });
    try {
      const response = await axios.post(`${API_URL}/robots`, {
        name,
        ip_address: ip,
        port
      });
      const savedRobots = [...get().savedRobots, response.data];
      set({ savedRobots, isLoading: false });
    } catch (error: any) {
      console.error('Error saving robot:', error);
      set({ error: error.message, isLoading: false });
    }
  },

  deleteRobot: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      await axios.delete(`${API_URL}/robots/${id}`);
      const savedRobots = get().savedRobots.filter(r => r.id !== id);
      set({ savedRobots, isLoading: false });
    } catch (error: any) {
      console.error('Error deleting robot:', error);
      set({ error: error.message, isLoading: false });
    }
  },

  connectToRobot: async (ip: string, port: number) => {
    set({ isConnecting: true, error: null });
    try {
      const response = await axios.post(`${API_URL}/robot/connect`, {
        ip_address: ip,
        port
      });
      if (response.data.success) {
        set({ 
          status: response.data.status, 
          isConnecting: false 
        });
        // Fetch gestures after connection
        get().fetchGestures();
        return true;
      } else {
        set({ error: response.data.message, isConnecting: false });
        return false;
      }
    } catch (error: any) {
      console.error('Error connecting to robot:', error);
      set({ error: error.message || 'Connection failed', isConnecting: false });
      return false;
    }
  },

  disconnectFromRobot: async () => {
    try {
      await axios.post(`${API_URL}/robot/disconnect`);
      set({ 
        status: { 
          connected: false, 
          ip_address: null, 
          battery_level: 0,
          temperature: 0,
          robot_name: 'NAO',
          uptime: 0,
          posture: 'Unknown'
        },
        sensors: null 
      });
    } catch (error: any) {
      console.error('Error disconnecting:', error);
    }
  },

  fetchStatus: async () => {
    try {
      const response = await axios.get(`${API_URL}/robot/status`);
      set({ status: response.data });
    } catch (error: any) {
      console.error('Error fetching status:', error);
    }
  },

  fetchSensors: async () => {
    try {
      const response = await axios.get(`${API_URL}/robot/sensors`);
      set({ sensors: response.data });
    } catch (error: any) {
      console.error('Error fetching sensors:', error);
    }
  },

  fetchGestures: async () => {
    try {
      const response = await axios.get(`${API_URL}/robot/gestures`);
      set({ gestures: response.data.gestures });
    } catch (error: any) {
      console.error('Error fetching gestures:', error);
    }
  },

  sendMoveCommand: async (x: number, y: number, theta: number) => {
    try {
      await axios.post(`${API_URL}/robot/move`, { x, y, theta });
    } catch (error: any) {
      console.error('Error sending move command:', error);
    }
  },

  stopMovement: async () => {
    try {
      await axios.post(`${API_URL}/robot/stop`);
    } catch (error: any) {
      console.error('Error stopping robot:', error);
    }
  },

  speak: async (text: string) => {
    try {
      await axios.post(`${API_URL}/robot/speak`, { text });
    } catch (error: any) {
      console.error('Error speaking:', error);
      throw error;
    }
  },

  executeGesture: async (gestureName: string) => {
    try {
      await axios.post(`${API_URL}/robot/gesture`, { gesture_name: gestureName });
    } catch (error: any) {
      console.error('Error executing gesture:', error);
      throw error;
    }
  },

  setCurrentRobot: (robot: RobotConfig | null) => {
    set({ currentRobot: robot });
  },

  clearError: () => {
    set({ error: null });
  }
}));
