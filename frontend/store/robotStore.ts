import { create } from 'zustand';
import axios from 'axios';

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
  connection_mode?: string;
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
  robotUrl: string | null;
  savedRobots: RobotConfig[];
  currentRobot: RobotConfig | null;
  status: RobotStatus | null;
  sensors: SensorData | null;
  gestures: Gesture[];
  isConnecting: boolean;
  isLoading: boolean;
  error: string | null;
  connectionError: string | null;
  
  // Actions
  setRobotUrl: (ip: string, port: number) => void;
  saveRobotLocally: (name: string, ip: string, port: number) => void;
  deleteRobotLocally: (id: string) => void;
  loadSavedRobots: () => void;
  connectToRobot: (ip: string, port: number) => Promise<{ success: boolean; message: string }>;
  disconnectFromRobot: () => Promise<void>;
  fetchStatus: () => Promise<void>;
  fetchSensors: () => Promise<void>;
  fetchGestures: () => Promise<void>;
  sendMoveCommand: (x: number, y: number, theta: number) => Promise<void>;
  stopMovement: () => Promise<void>;
  speak: (text: string) => Promise<void>;
  executeGesture: (gestureName: string) => Promise<void>;
  getCameraFrame: () => Promise<string | null>;
  setCurrentRobot: (robot: RobotConfig | null) => void;
  clearError: () => void;
  clearConnectionError: () => void;
}

// Storage key for saved robots
const STORAGE_KEY = 'nao_saved_robots';

// Helper to get/set from localStorage (works on web) or AsyncStorage
const storage = {
  get: (key: string): RobotConfig[] => {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        const data = window.localStorage.getItem(key);
        return data ? JSON.parse(data) : [];
      }
    } catch (e) {
      console.error('Storage get error:', e);
    }
    return [];
  },
  set: (key: string, value: RobotConfig[]) => {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        window.localStorage.setItem(key, JSON.stringify(value));
      }
    } catch (e) {
      console.error('Storage set error:', e);
    }
  }
};

export const useRobotStore = create<RobotStore>((set, get) => ({
  robotUrl: null,
  savedRobots: [],
  currentRobot: null,
  status: null,
  sensors: null,
  gestures: [],
  isConnecting: false,
  isLoading: false,
  error: null,
  connectionError: null,

  setRobotUrl: (ip: string, port: number) => {
    set({ robotUrl: `http://${ip}:${port}` });
  },

  loadSavedRobots: () => {
    const robots = storage.get(STORAGE_KEY);
    set({ savedRobots: robots });
  },

  saveRobotLocally: (name: string, ip: string, port: number) => {
    const robots = get().savedRobots;
    const newRobot: RobotConfig = {
      id: Date.now().toString(),
      name,
      ip_address: ip,
      port,
      created_at: new Date().toISOString()
    };
    const updated = [...robots, newRobot];
    storage.set(STORAGE_KEY, updated);
    set({ savedRobots: updated });
  },

  deleteRobotLocally: (id: string) => {
    const robots = get().savedRobots.filter(r => r.id !== id);
    storage.set(STORAGE_KEY, robots);
    set({ savedRobots: robots });
  },

  connectToRobot: async (ip: string, port: number) => {
    const url = `http://${ip}:${port}`;
    set({ isConnecting: true, connectionError: null, robotUrl: url });
    
    try {
      // Test connection by calling the status endpoint
      const response = await axios.post(`${url}/api/robot/connect`, {}, { 
        timeout: 10000,
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (response.data.success) {
        set({ 
          status: response.data.status, 
          isConnecting: false,
          connectionError: null
        });
        // Fetch gestures after connection
        get().fetchGestures();
        return { success: true, message: response.data.message || 'Connected!' };
      } else {
        const errorMsg = response.data.message || 'Connection failed';
        set({ 
          connectionError: errorMsg, 
          isConnecting: false,
          robotUrl: null
        });
        return { success: false, message: errorMsg };
      }
    } catch (error: any) {
      console.error('Error connecting to robot:', error);
      let errorMsg = 'Cannot connect to NAO robot.\n\n';
      
      if (error.code === 'ECONNREFUSED' || error.message?.includes('Network')) {
        errorMsg += 'Make sure:\n';
        errorMsg += '1. NAO REST server is running on the robot\n';
        errorMsg += '2. Your phone is on the same WiFi as NAO\n';
        errorMsg += '3. IP address is correct: ' + ip;
      } else if (error.code === 'ETIMEDOUT' || error.message?.includes('timeout')) {
        errorMsg += 'Connection timed out. Check if NAO is reachable.';
      } else {
        errorMsg += error.message || 'Unknown error';
      }
      
      set({ connectionError: errorMsg, isConnecting: false, robotUrl: null });
      return { success: false, message: errorMsg };
    }
  },

  disconnectFromRobot: async () => {
    const url = get().robotUrl;
    if (url) {
      try {
        await axios.post(`${url}/api/robot/disconnect`, {}, { timeout: 5000 });
      } catch (e) {
        console.log('Disconnect error (ignored):', e);
      }
    }
    set({ 
      status: null,
      sensors: null,
      robotUrl: null,
      connectionError: null
    });
  },

  fetchStatus: async () => {
    const url = get().robotUrl;
    if (!url) return;
    
    try {
      const response = await axios.get(`${url}/api/robot/status`, { timeout: 5000 });
      set({ status: response.data });
    } catch (error: any) {
      console.error('Error fetching status:', error);
      // If we can't reach the robot, mark as disconnected
      if (error.code === 'ECONNREFUSED' || error.message?.includes('Network')) {
        set({ status: null, robotUrl: null });
      }
    }
  },

  fetchSensors: async () => {
    const url = get().robotUrl;
    if (!url) return;
    
    try {
      const response = await axios.get(`${url}/api/robot/sensors`, { timeout: 5000 });
      set({ sensors: response.data });
    } catch (error: any) {
      console.error('Error fetching sensors:', error);
    }
  },

  fetchGestures: async () => {
    const url = get().robotUrl;
    if (!url) return;
    
    try {
      const response = await axios.get(`${url}/api/robot/gestures`, { timeout: 5000 });
      set({ gestures: response.data.gestures });
    } catch (error: any) {
      console.error('Error fetching gestures:', error);
      // Set default gestures
      set({ 
        gestures: [
          { name: "wave", description: "Wave hand", icon: "hand-wave" },
          { name: "sit", description: "Sit down", icon: "seat" },
          { name: "stand", description: "Stand up", icon: "human" },
          { name: "bow", description: "Bow", icon: "human-greeting" },
          { name: "dance", description: "Dance", icon: "music" },
          { name: "handshake", description: "Handshake", icon: "handshake" },
          { name: "yes", description: "Nod yes", icon: "check" },
          { name: "no", description: "Shake head no", icon: "close" },
          { name: "think", description: "Thinking pose", icon: "brain" },
          { name: "celebrate", description: "Celebrate", icon: "party-popper" }
        ]
      });
    }
  },

  sendMoveCommand: async (x: number, y: number, theta: number) => {
    const url = get().robotUrl;
    if (!url) return;
    
    try {
      await axios.post(`${url}/api/robot/move`, { x, y, theta }, { timeout: 3000 });
    } catch (error: any) {
      console.error('Error sending move command:', error);
    }
  },

  stopMovement: async () => {
    const url = get().robotUrl;
    if (!url) return;
    
    try {
      await axios.post(`${url}/api/robot/stop`, {}, { timeout: 3000 });
    } catch (error: any) {
      console.error('Error stopping robot:', error);
    }
  },

  speak: async (text: string) => {
    const url = get().robotUrl;
    if (!url) throw new Error('Not connected');
    
    try {
      const response = await axios.post(`${url}/api/robot/speak`, { text }, { timeout: 30000 });
      if (!response.data.success) {
        throw new Error(response.data.message);
      }
    } catch (error: any) {
      console.error('Error speaking:', error);
      throw error;
    }
  },

  executeGesture: async (gestureName: string) => {
    const url = get().robotUrl;
    if (!url) throw new Error('Not connected');
    
    try {
      const response = await axios.post(`${url}/api/robot/gesture`, { gesture_name: gestureName }, { timeout: 30000 });
      if (!response.data.success) {
        throw new Error(response.data.message);
      }
    } catch (error: any) {
      console.error('Error executing gesture:', error);
      throw error;
    }
  },

  getCameraFrame: async () => {
    const url = get().robotUrl;
    if (!url) return null;
    
    try {
      const response = await axios.get(`${url}/api/robot/camera/frame`, { timeout: 10000 });
      return response.data.frame;
    } catch (error: any) {
      console.error('Error getting camera frame:', error);
      return null;
    }
  },

  setCurrentRobot: (robot: RobotConfig | null) => {
    set({ currentRobot: robot });
  },

  clearError: () => {
    set({ error: null });
  },

  clearConnectionError: () => {
    set({ connectionError: null });
  }
}));
