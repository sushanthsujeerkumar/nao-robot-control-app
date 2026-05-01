import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS, SPACING, BORDER_RADIUS, FONT_SIZES } from '../../constants/theme';
import { useRobotStore } from '../../store/robotStore';
import { Card } from '../../components/Card';
import axios from 'axios';

export default function FunctionsScreen() {
  const { robotUrl, status } = useRobotStore();
  
  const [fallDetection, setFallDetection] = useState({
    status: 'idle',
    message: 'Fall detection is not active',
    lastAlert: null,
  });
  
  const [exercise, setExercise] = useState({
    status: 'idle',
    message: 'Exercise session not started',
    currentExercise: '',
    waitingForResponse: false,
  });

  const [automation, setAutomation] = useState({
    lightStatus: false,
    esp32Connected: false,
    lastAction: '',
    esp32Ip: '172.18.16.43',
    isListening: false,
  });

  const [storytelling, setStorytelling] = useState({
    status: 'idle',
    message: 'Select a story to play',
    currentStory: '',
    isPlaying: false,
  });
  
  const [isLoading, setIsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('fall');
  const [esp32IpInput, setEsp32IpInput] = useState('172.18.16.43');
  const pollingRef = useRef(null);

  const stories = [
    { id: 1, name: 'The Bear and the Bee', icon: '🐻', duration: '3 min' },
    { id: 2, name: 'The Lion and the Mouse', icon: '🦁', duration: '2 min' },
    { id: 3, name: 'The Tortoise and the Hare', icon: '🐢', duration: '3 min' },
    { id: 4, name: 'The Fox and the Grapes', icon: '🦊', duration: '2 min' },
    { id: 5, name: 'The Ant and the Grasshopper', icon: '🐜', duration: '3 min' },
  ];

  const isConnected = status?.connected && robotUrl;

  useEffect(() => {
    if (activeTab === 'fall' && (fallDetection.status === 'monitoring' || fallDetection.status === 'person_detected' || fallDetection.status === 'checking')) {
      pollingRef.current = setInterval(async () => {
        try {
          const response = await axios.get(`${robotUrl}/api/robot/fall_detection/status`, { timeout: 5000 });
          if (response.data) {
            setFallDetection({
              status: response.data.status || 'monitoring',
              message: response.data.message || 'Monitoring...',
              lastAlert: response.data.last_alert,
            });
          }
        } catch (error) {}
      }, 2000);
    } else if (activeTab === 'exercise' && exercise.status !== 'idle' && exercise.status !== 'session_end') {
      pollingRef.current = setInterval(async () => {
        try {
          const response = await axios.get(`${robotUrl}/api/robot/exercise/status`, { timeout: 5000 });
          if (response.data) {
            setExercise({
              status: response.data.status || 'idle',
              message: response.data.message || '',
              currentExercise: response.data.current_exercise || '',
              waitingForResponse: response.data.waiting_for_response || false,
            });
          }
        } catch (error) {}
      }, 1500);
    }

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [fallDetection.status, exercise.status, activeTab, robotUrl]);

  const startFallDetection = async () => {
    if (!robotUrl) {
      Alert.alert('Not Connected', 'Please connect to NAO robot first.');
      return;
    }
    setIsLoading(true);
    try {
      const response = await axios.post(`${robotUrl}/api/robot/fall_detection/start`, {}, { timeout: 10000 });
      if (response.data.success) {
        setFallDetection({ status: 'monitoring', message: 'Monitoring for fallen persons...', lastAlert: null });
      } else {
        Alert.alert('Error', response.data.message || 'Failed to start');
      }
    } catch (error) {
      Alert.alert('Error', error.message || 'Failed to start fall detection');
    } finally {
      setIsLoading(false);
    }
  };

  const stopFallDetection = async () => {
    setIsLoading(true);
    try {
      await axios.post(`${robotUrl}/api/robot/fall_detection/stop`, {}, { timeout: 10000 });
    } catch (error) {}
    setFallDetection({ status: 'idle', message: 'Fall detection stopped', lastAlert: null });
    setIsLoading(false);
  };

  const testFallDetection = async () => {
    if (!robotUrl) {
      Alert.alert('Not Connected', 'Please connect to NAO robot first.');
      return;
    }
    setIsLoading(true);
    try {
      const response = await axios.post(`${robotUrl}/api/robot/fall_detection/test`, {}, { timeout: 60000 });
      Alert.alert('Test Complete', response.data.results?.join('\n') || 'Test finished');
    } catch (error) {
      Alert.alert('Error', error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const startExercise = async () => {
    if (!robotUrl) {
      Alert.alert('Not Connected', 'Please connect to NAO robot first.');
      return;
    }
    setIsLoading(true);
    try {
      const response = await axios.post(`${robotUrl}/api/robot/exercise/start`, {}, { timeout: 10000 });
      if (response.data.success) {
        setExercise({
          status: 'greeting',
          message: 'Exercise session starting...',
          currentExercise: '',
          waitingForResponse: false,
        });
      } else {
        Alert.alert('Error', response.data.message || 'Failed to start');
      }
    } catch (error) {
      Alert.alert('Error', error.message || 'Failed to start exercise');
    } finally {
      setIsLoading(false);
    }
  };

  const stopExercise = async () => {
    setIsLoading(true);
    try {
      await axios.post(`${robotUrl}/api/robot/exercise/stop`, {}, { timeout: 10000 });
    } catch (error) {}
    setExercise({
      status: 'idle',
      message: 'Exercise session stopped',
      currentExercise: '',
      waitingForResponse: false,
    });
    setIsLoading(false);
  };

  const sendExerciseResponse = async (response) => {
    if (!robotUrl) return;
    setIsLoading(true);
    try {
      await axios.post(`${robotUrl}/api/robot/exercise/respond`, { response }, { timeout: 10000 });
    } catch (error) {
      Alert.alert('Error', error.message);
    } finally {
      setIsLoading(false);
    }
  };

  // Automation Functions
  const controlLight = async (action) => {
    if (!robotUrl) {
      Alert.alert('Not Connected', 'Please connect to NAO robot first.');
      return;
    }
    setIsLoading(true);
    try {
      const response = await axios.post(`${robotUrl}/api/automation/light`, { action, esp32_ip: automation.esp32Ip }, { timeout: 15000 });
      if (response.data.success) {
        setAutomation(prev => ({
          ...prev,
          lightStatus: action === 'on',
          esp32Connected: true,
          lastAction: `Light turned ${action} at ${new Date().toLocaleTimeString()}`,
        }));
      } else {
        Alert.alert('Error', response.data.message || 'Failed to control light');
        setAutomation(prev => ({ ...prev, esp32Connected: false }));
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to control light. Check ESP32 connection.');
      setAutomation(prev => ({ ...prev, esp32Connected: false }));
    } finally {
      setIsLoading(false);
    }
  };

  const voiceControlLight = async (action) => {
    if (!robotUrl) {
      Alert.alert('Not Connected', 'Please connect to NAO robot first.');
      return;
    }
    setIsLoading(true);
    try {
      const response = await axios.post(`${robotUrl}/api/automation/voice_light`, { action, esp32_ip: automation.esp32Ip }, { timeout: 20000 });
      if (response.data.success) {
        setAutomation(prev => ({
          ...prev,
          lightStatus: action === 'on',
          esp32Connected: true,
          lastAction: `NAO said: "${response.data.speech}" at ${new Date().toLocaleTimeString()}`,
        }));
      } else {
        Alert.alert('Error', response.data.message || 'Failed to control light');
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to control light via voice.');
    } finally {
      setIsLoading(false);
    }
  };

  const updateEsp32Ip = async () => {
    if (!robotUrl) {
      Alert.alert('Not Connected', 'Please connect to NAO robot first.');
      return;
    }
    if (!esp32IpInput || esp32IpInput.trim() === '') {
      Alert.alert('Error', 'Please enter a valid IP address');
      return;
    }
    setIsLoading(true);
    try {
      const response = await axios.post(`${robotUrl}/api/automation/set_ip`, { esp32_ip: esp32IpInput }, { timeout: 10000 });
      if (response.data.success) {
        setAutomation(prev => ({ ...prev, esp32Ip: esp32IpInput, esp32Connected: response.data.connected }));
        Alert.alert('Success', `ESP32 IP updated to ${esp32IpInput}`);
      } else {
        Alert.alert('Error', response.data.message || 'Failed to update IP');
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to update ESP32 IP');
    } finally {
      setIsLoading(false);
    }
  };

  const startVoiceListening = async () => {
    if (!robotUrl) {
      Alert.alert('Not Connected', 'Please connect to NAO robot first.');
      return;
    }
    setAutomation(prev => ({ ...prev, isListening: true }));
    try {
      const response = await axios.post(`${robotUrl}/api/automation/listen_command`, { esp32_ip: automation.esp32Ip }, { timeout: 30000 });
      if (response.data.success) {
        setAutomation(prev => ({
          ...prev,
          lightStatus: response.data.light_status,
          esp32Connected: true,
          lastAction: `Voice: "${response.data.command}" - ${response.data.action} at ${new Date().toLocaleTimeString()}`,
          isListening: false,
        }));
      } else {
        Alert.alert('Info', response.data.message || 'No command detected');
        setAutomation(prev => ({ ...prev, isListening: false }));
      }
    } catch (error) {
      Alert.alert('Error', 'Voice listening failed');
      setAutomation(prev => ({ ...prev, isListening: false }));
    }
  };

  const checkESP32Status = async () => {
    if (!robotUrl) return;
    try {
      const response = await axios.get(`${robotUrl}/api/automation/status`, { timeout: 5000 });
      setAutomation(prev => ({
        ...prev,
        esp32Connected: response.data.esp32_connected || false,
        lightStatus: response.data.light_status || false,
      }));
    } catch (error) {
      setAutomation(prev => ({ ...prev, esp32Connected: false }));
    }
  };

  useEffect(() => {
    if (activeTab === 'automation' && robotUrl) {
      checkESP32Status();
    }
  }, [activeTab, robotUrl]);

  // Storytelling Functions
  const playStory = async (storyId, storyName) => {
    if (!robotUrl) {
      Alert.alert('Not Connected', 'Please connect to NAO robot first.');
      return;
    }
    setIsLoading(true);
    setStorytelling(prev => ({
      ...prev,
      status: 'loading',
      message: `Loading "${storyName}"...`,
      currentStory: storyName,
    }));
    try {
      const response = await axios.post(`${robotUrl}/api/storytelling/play`, { story_id: storyId }, { timeout: 120000 });
      if (response.data.success) {
        setStorytelling(prev => ({
          ...prev,
          status: 'playing',
          message: `Now playing: ${storyName}`,
          isPlaying: true,
        }));
        // Poll for status
        pollStoryStatus();
      } else {
        Alert.alert('Error', response.data.message || 'Failed to play story');
        setStorytelling(prev => ({ ...prev, status: 'idle', message: 'Select a story to play', isPlaying: false }));
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to play story');
      setStorytelling(prev => ({ ...prev, status: 'idle', message: 'Select a story to play', isPlaying: false }));
    } finally {
      setIsLoading(false);
    }
  };

  const stopStory = async () => {
    if (!robotUrl) return;
    setIsLoading(true);
    try {
      await axios.post(`${robotUrl}/api/storytelling/stop`, {}, { timeout: 10000 });
      setStorytelling({
        status: 'idle',
        message: 'Story stopped',
        currentStory: '',
        isPlaying: false,
      });
    } catch (error) {
      Alert.alert('Error', 'Failed to stop story');
    } finally {
      setIsLoading(false);
    }
  };

  const pollStoryStatus = async () => {
    if (!robotUrl) return;
    try {
      const response = await axios.get(`${robotUrl}/api/storytelling/status`, { timeout: 5000 });
      setStorytelling(prev => ({
        ...prev,
        status: response.data.status || 'idle',
        message: response.data.message || 'Select a story to play',
        isPlaying: response.data.is_playing || false,
      }));
      if (response.data.is_playing) {
        setTimeout(pollStoryStatus, 3000);
      }
    } catch (error) {
      // Ignore polling errors
    }
  };

  const getExerciseStatusColor = () => {
    switch (exercise.status) {
      case 'squat':
      case 'arm_stretch':
        return COLORS.success;
      case 'readiness':
      case 'continue_check':
        return COLORS.warning;
      case 'cooldown':
      case 'feedback':
        return COLORS.primary;
      case 'error':
        return COLORS.error;
      default:
        return COLORS.textMuted;
    }
  };

  const getFallStatusColor = () => {
    switch (fallDetection.status) {
      case 'monitoring': return COLORS.primary;
      case 'person_detected':
      case 'checking': return COLORS.warning;
      case 'alert_sent':
      case 'error': return COLORS.error;
      default: return COLORS.textMuted;
    }
  };

  const isFallActive = fallDetection.status !== 'idle' && fallDetection.status !== 'error';
  const isExerciseActive = exercise.status !== 'idle' && exercise.status !== 'session_end';

  return (
    <SafeAreaView style={styles.container} edges={['left', 'right']}>
      <ScrollView style={styles.scrollView} contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <View style={styles.header}>
          <Ionicons name="shield-checkmark" size={32} color={COLORS.primary} />
          <Text style={styles.headerTitle}>Safety Functions</Text>
        </View>

        {!isConnected && (
          <Card style={styles.warningCard}>
            <View style={styles.warningContent}>
              <Ionicons name="warning" size={24} color={COLORS.warning} />
              <Text style={styles.warningText}>Connect to NAO robot to use functions</Text>
            </View>
          </Card>
        )}

        <View style={styles.tabContainer}>
          <TouchableOpacity
            style={[styles.tab, activeTab === 'fall' && styles.tabActive]}
            onPress={() => setActiveTab('fall')}
          >
            <Ionicons name="body" size={18} color={activeTab === 'fall' ? COLORS.text : COLORS.textMuted} />
            <Text style={[styles.tabText, activeTab === 'fall' && styles.tabTextActive]}>Fall</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.tab, activeTab === 'exercise' && styles.tabActive]}
            onPress={() => setActiveTab('exercise')}
          >
            <Ionicons name="fitness" size={18} color={activeTab === 'exercise' ? COLORS.text : COLORS.textMuted} />
            <Text style={[styles.tabText, activeTab === 'exercise' && styles.tabTextActive]}>Exercise</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.tab, activeTab === 'automation' && styles.tabActive]}
            onPress={() => setActiveTab('automation')}
          >
            <Ionicons name="bulb" size={18} color={activeTab === 'automation' ? COLORS.text : COLORS.textMuted} />
            <Text style={[styles.tabText, activeTab === 'automation' && styles.tabTextActive]}>Light</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.tab, activeTab === 'story' && styles.tabActive]}
            onPress={() => setActiveTab('story')}
          >
            <Ionicons name="book" size={18} color={activeTab === 'story' ? COLORS.text : COLORS.textMuted} />
            <Text style={[styles.tabText, activeTab === 'story' && styles.tabTextActive]}>Story</Text>
          </TouchableOpacity>
        </View>

        {activeTab === 'fall' && (
          <>
            <Card style={styles.card}>
              <View style={styles.cardHeader}>
                <View style={styles.cardTitleRow}>
                  <Ionicons name="body" size={24} color={COLORS.primary} />
                  <Text style={styles.cardTitle}>Fall Detection</Text>
                </View>
                <View style={[styles.statusBadge, { backgroundColor: getFallStatusColor() + '30' }]}>
                  <View style={[styles.statusDot, { backgroundColor: getFallStatusColor() }]} />
                  <Text style={[styles.statusText, { color: getFallStatusColor() }]}>
                    {fallDetection.status === 'idle' ? 'Inactive' : fallDetection.status.replace('_', ' ').toUpperCase()}
                  </Text>
                </View>
              </View>

              <Text style={styles.description}>
                Monitors for persons lying horizontal. If detected, NAO will check on them and send alerts.
              </Text>

              <View style={[styles.statusDisplay, { borderColor: getFallStatusColor() }]}>
                <Ionicons name={fallDetection.status === 'monitoring' ? 'eye' : 'shield-outline'} size={40} color={getFallStatusColor()} />
                <Text style={styles.statusMessage}>{fallDetection.message}</Text>
                {fallDetection.lastAlert && <Text style={styles.lastAlert}>Last alert: {fallDetection.lastAlert}</Text>}
              </View>

              <View style={styles.buttonRow}>
                {!isFallActive ? (
                  <TouchableOpacity style={[styles.primaryButton, !isConnected && styles.buttonDisabled]} onPress={startFallDetection} disabled={!isConnected || isLoading}>
                    {isLoading ? <ActivityIndicator color={COLORS.text} /> : (
                      <>
                        <Ionicons name="play" size={20} color={COLORS.text} />
                        <Text style={styles.buttonText}>Start Monitoring</Text>
                      </>
                    )}
                  </TouchableOpacity>
                ) : (
                  <TouchableOpacity style={styles.stopButton} onPress={stopFallDetection} disabled={isLoading}>
                    {isLoading ? <ActivityIndicator color={COLORS.text} /> : (
                      <>
                        <Ionicons name="stop" size={20} color={COLORS.text} />
                        <Text style={styles.buttonText}>Stop Monitoring</Text>
                      </>
                    )}
                  </TouchableOpacity>
                )}
              </View>

              <TouchableOpacity style={[styles.testButton, !isConnected && styles.buttonDisabled]} onPress={testFallDetection} disabled={!isConnected || isLoading}>
                <Ionicons name="flask" size={18} color={COLORS.primary} />
                <Text style={styles.testButtonText}>Test Alert System</Text>
              </TouchableOpacity>
            </Card>

            <Card style={styles.infoCard}>
              <View style={styles.infoHeader}>
                <Ionicons name="mail" size={20} color={COLORS.textSecondary} />
                <Text style={styles.infoTitle}>Email Alert</Text>
              </View>
              <Text style={styles.infoText}>Alerts sent to: sushanthsujeerkumar@gmail.com</Text>
            </Card>
          </>
        )}

        {activeTab === 'exercise' && (
          <>
            <Card style={styles.card}>
              <View style={styles.cardHeader}>
                <View style={styles.cardTitleRow}>
                  <Ionicons name="fitness" size={24} color={COLORS.success} />
                  <Text style={styles.cardTitle}>Exercise Session</Text>
                </View>
                <View style={[styles.statusBadge, { backgroundColor: getExerciseStatusColor() + '30' }]}>
                  <View style={[styles.statusDot, { backgroundColor: getExerciseStatusColor() }]} />
                  <Text style={[styles.statusText, { color: getExerciseStatusColor() }]}>
                    {exercise.status === 'idle' ? 'Ready' : exercise.status.replace('_', ' ').toUpperCase()}
                  </Text>
                </View>
              </View>

              <Text style={styles.description}>
                Guided exercise session with NAO. Includes squats, arm stretches, and cooldown breathing.
              </Text>

              <View style={styles.stepsList}>
                <View style={styles.stepItem}>
                  <View style={[styles.stepNumber, exercise.status === 'squat' && styles.stepActive]}>
                    <Text style={styles.stepNumberText}>1</Text>
                  </View>
                  <Text style={styles.stepText}>Supported Squats (3 reps)</Text>
                </View>
                <View style={styles.stepItem}>
                  <View style={[styles.stepNumber, exercise.status === 'arm_stretch' && styles.stepActive]}>
                    <Text style={styles.stepNumberText}>2</Text>
                  </View>
                  <Text style={styles.stepText}>Arm Stretches (3 reps)</Text>
                </View>
                <View style={styles.stepItem}>
                  <View style={[styles.stepNumber, exercise.status === 'cooldown' && styles.stepActive]}>
                    <Text style={styles.stepNumberText}>3</Text>
                  </View>
                  <Text style={styles.stepText}>Cooldown and Breathing</Text>
                </View>
              </View>

              <View style={[styles.statusDisplay, { borderColor: getExerciseStatusColor() }]}>
                <Ionicons 
                  name={
                    exercise.status === 'squat' || exercise.status === 'arm_stretch' ? 'barbell' :
                    exercise.status === 'cooldown' ? 'leaf' :
                    exercise.status === 'feedback' ? 'happy' :
                    'fitness-outline'
                  } 
                  size={40} 
                  color={getExerciseStatusColor()} 
                />
                <Text style={styles.statusMessage}>{exercise.message}</Text>
                {exercise.currentExercise ? (
                  <Text style={styles.currentExercise}>Current: {exercise.currentExercise}</Text>
                ) : null}
              </View>

              {exercise.waitingForResponse && (
                <View style={styles.responseContainer}>
                  <Text style={styles.responsePrompt}>NAO is waiting for your response:</Text>
                  <View style={styles.responseButtons}>
                    <TouchableOpacity style={styles.yesButton} onPress={() => sendExerciseResponse('yes')} disabled={isLoading}>
                      <Ionicons name="checkmark" size={24} color={COLORS.text} />
                      <Text style={styles.responseButtonText}>Yes</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={styles.noButton} onPress={() => sendExerciseResponse('no')} disabled={isLoading}>
                      <Ionicons name="close" size={24} color={COLORS.text} />
                      <Text style={styles.responseButtonText}>No</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={styles.stopResponseButton} onPress={() => sendExerciseResponse('stop')} disabled={isLoading}>
                      <Ionicons name="hand-left" size={24} color={COLORS.text} />
                      <Text style={styles.responseButtonText}>Stop</Text>
                    </TouchableOpacity>
                  </View>
                </View>
              )}

              <View style={styles.buttonRow}>
                {!isExerciseActive ? (
                  <TouchableOpacity style={[styles.successButton, !isConnected && styles.buttonDisabled]} onPress={startExercise} disabled={!isConnected || isLoading}>
                    {isLoading ? <ActivityIndicator color={COLORS.text} /> : (
                      <>
                        <Ionicons name="play" size={20} color={COLORS.text} />
                        <Text style={styles.buttonText}>Start Exercise</Text>
                      </>
                    )}
                  </TouchableOpacity>
                ) : (
                  <TouchableOpacity style={styles.stopButton} onPress={stopExercise} disabled={isLoading}>
                    {isLoading ? <ActivityIndicator color={COLORS.text} /> : (
                      <>
                        <Ionicons name="stop" size={20} color={COLORS.text} />
                        <Text style={styles.buttonText}>Stop Exercise</Text>
                      </>
                    )}
                  </TouchableOpacity>
                )}
              </View>
            </Card>

            <Card style={styles.infoCard}>
              <View style={styles.infoHeader}>
                <Ionicons name="information-circle" size={20} color={COLORS.textSecondary} />
                <Text style={styles.infoTitle}>How It Works</Text>
              </View>
              <Text style={styles.infoText}>
                NAO guides you through gentle exercises with voice instructions. Respond using the buttons or by speaking to NAO.
              </Text>
            </Card>
          </>
        )}

        {activeTab === 'automation' && (
          <>
            <Card style={styles.card}>
              <View style={styles.cardHeader}>
                <View style={styles.cardTitleRow}>
                  <Ionicons name="bulb" size={24} color={automation.lightStatus ? COLORS.warning : COLORS.textMuted} />
                  <Text style={styles.cardTitle}>Smart Light Control</Text>
                </View>
                <View style={[styles.statusBadge, { backgroundColor: automation.esp32Connected ? COLORS.success + '30' : COLORS.error + '30' }]}>
                  <View style={[styles.statusDot, { backgroundColor: automation.esp32Connected ? COLORS.success : COLORS.error }]} />
                  <Text style={[styles.statusText, { color: automation.esp32Connected ? COLORS.success : COLORS.error }]}>
                    {automation.esp32Connected ? 'ESP32 Connected' : 'ESP32 Offline'}
                  </Text>
                </View>
              </View>

              <Text style={styles.description}>
                Control your room light using NAO robot. NAO will speak and then turn the light on or off via ESP32.
              </Text>

              <Text style={styles.sectionTitle}>ESP32 IP Address</Text>
              <View style={styles.ipInputRow}>
                <TextInput
                  style={styles.ipInput}
                  value={esp32IpInput}
                  onChangeText={setEsp32IpInput}
                  placeholder="Enter ESP32 IP"
                  placeholderTextColor={COLORS.textMuted}
                  keyboardType="numeric"
                />
                <TouchableOpacity 
                  style={[styles.ipSaveButton, !isConnected && styles.buttonDisabled]} 
                  onPress={updateEsp32Ip} 
                  disabled={!isConnected || isLoading}
                >
                  <Text style={styles.ipSaveText}>Save</Text>
                </TouchableOpacity>
              </View>

              <View style={[styles.lightStatusDisplay, { backgroundColor: automation.lightStatus ? COLORS.warning + '20' : COLORS.surfaceLight }]}>
                <Ionicons 
                  name={automation.lightStatus ? 'bulb' : 'bulb-outline'} 
                  size={80} 
                  color={automation.lightStatus ? COLORS.warning : COLORS.textMuted} 
                />
                <Text style={[styles.lightStatusText, { color: automation.lightStatus ? COLORS.warning : COLORS.textMuted }]}>
                  Light is {automation.lightStatus ? 'ON' : 'OFF'}
                </Text>
                {automation.lastAction ? (
                  <Text style={styles.lastActionText}>{automation.lastAction}</Text>
                ) : null}
              </View>

              <Text style={styles.sectionTitle}>Voice Listen (Say command to NAO)</Text>
              <Text style={styles.voiceDescription}>
                Tap the button below, then say "turn on the light" or "turn off the light" to NAO
              </Text>
              <TouchableOpacity 
                style={[styles.listenButton, automation.isListening && styles.listeningActive, !isConnected && styles.buttonDisabled]} 
                onPress={startVoiceListening} 
                disabled={!isConnected || automation.isListening}
              >
                {automation.isListening ? (
                  <>
                    <ActivityIndicator color={COLORS.text} />
                    <Text style={styles.listenButtonText}>Listening... Say your command</Text>
                  </>
                ) : (
                  <>
                    <Ionicons name="ear" size={28} color={COLORS.text} />
                    <Text style={styles.listenButtonText}>Tap to Listen for Voice Command</Text>
                  </>
                )}
              </TouchableOpacity>

              <Text style={styles.sectionTitle}>Manual Control</Text>
              <View style={styles.lightButtonsRow}>
                <TouchableOpacity 
                  style={[styles.lightOnButton, !isConnected && styles.buttonDisabled]} 
                  onPress={() => controlLight('on')} 
                  disabled={!isConnected || isLoading}
                >
                  {isLoading ? <ActivityIndicator color={COLORS.text} /> : (
                    <>
                      <Ionicons name="sunny" size={24} color={COLORS.text} />
                      <Text style={styles.buttonText}>Turn ON</Text>
                    </>
                  )}
                </TouchableOpacity>
                <TouchableOpacity 
                  style={[styles.lightOffButton, !isConnected && styles.buttonDisabled]} 
                  onPress={() => controlLight('off')} 
                  disabled={!isConnected || isLoading}
                >
                  {isLoading ? <ActivityIndicator color={COLORS.text} /> : (
                    <>
                      <Ionicons name="moon" size={24} color={COLORS.text} />
                      <Text style={styles.buttonText}>Turn OFF</Text>
                    </>
                  )}
                </TouchableOpacity>
              </View>

              <Text style={styles.sectionTitle}>Voice Control (NAO Speaks)</Text>
              <Text style={styles.voiceDescription}>
                NAO will say the command and then control the light
              </Text>
              <View style={styles.lightButtonsRow}>
                <TouchableOpacity 
                  style={[styles.voiceOnButton, !isConnected && styles.buttonDisabled]} 
                  onPress={() => voiceControlLight('on')} 
                  disabled={!isConnected || isLoading}
                >
                  {isLoading ? <ActivityIndicator color={COLORS.text} /> : (
                    <>
                      <Ionicons name="mic" size={20} color={COLORS.text} />
                      <Text style={styles.voiceButtonText}>Turn on light</Text>
                    </>
                  )}
                </TouchableOpacity>
                <TouchableOpacity 
                  style={[styles.voiceOffButton, !isConnected && styles.buttonDisabled]} 
                  onPress={() => voiceControlLight('off')} 
                  disabled={!isConnected || isLoading}
                >
                  {isLoading ? <ActivityIndicator color={COLORS.text} /> : (
                    <>
                      <Ionicons name="mic" size={20} color={COLORS.text} />
                      <Text style={styles.voiceButtonText}>Turn off light</Text>
                    </>
                  )}
                </TouchableOpacity>
              </View>
            </Card>

            <Card style={styles.infoCard}>
              <View style={styles.infoHeader}>
                <Ionicons name="hardware-chip" size={20} color={COLORS.textSecondary} />
                <Text style={styles.infoTitle}>ESP32 Setup</Text>
              </View>
              <Text style={styles.infoText}>
                ESP32 IP: {automation.esp32Ip}{'\n'}
                LED Pin: GPIO 4{'\n'}
                WiFi: ll_cst_labs
              </Text>
            </Card>
          </>
        )}

        {activeTab === 'story' && (
          <>
            <Card style={styles.card}>
              <View style={styles.cardHeader}>
                <View style={styles.cardTitleRow}>
                  <Ionicons name="book" size={24} color={COLORS.primary} />
                  <Text style={styles.cardTitle}>Storytelling</Text>
                </View>
                <View style={[styles.statusBadge, { backgroundColor: storytelling.isPlaying ? COLORS.success + '30' : COLORS.textMuted + '30' }]}>
                  <View style={[styles.statusDot, { backgroundColor: storytelling.isPlaying ? COLORS.success : COLORS.textMuted }]} />
                  <Text style={[styles.statusText, { color: storytelling.isPlaying ? COLORS.success : COLORS.textMuted }]}>
                    {storytelling.isPlaying ? 'Playing' : 'Ready'}
                  </Text>
                </View>
              </View>

              <Text style={styles.description}>
                NAO will tell you a story with voice and gestures. Select a story below to begin.
              </Text>

              {storytelling.isPlaying && (
                <View style={[styles.statusDisplay, { borderColor: COLORS.success }]}>
                  <Ionicons name="volume-high" size={50} color={COLORS.success} />
                  <Text style={styles.statusMessage}>{storytelling.message}</Text>
                  <Text style={styles.currentExercise}>{storytelling.currentStory}</Text>
                </View>
              )}

              {storytelling.isPlaying ? (
                <TouchableOpacity 
                  style={[styles.stopButton, !isConnected && styles.buttonDisabled]} 
                  onPress={stopStory} 
                  disabled={!isConnected || isLoading}
                >
                  {isLoading ? <ActivityIndicator color={COLORS.text} /> : (
                    <>
                      <Ionicons name="stop-circle" size={24} color={COLORS.text} />
                      <Text style={styles.buttonText}>Stop Story</Text>
                    </>
                  )}
                </TouchableOpacity>
              ) : (
                <View style={styles.storiesGrid}>
                  {stories.map((story) => (
                    <TouchableOpacity
                      key={story.id}
                      style={[styles.storyCard, !isConnected && styles.buttonDisabled]}
                      onPress={() => playStory(story.id, story.name)}
                      disabled={!isConnected || isLoading}
                    >
                      <Text style={styles.storyIcon}>{story.icon}</Text>
                      <Text style={styles.storyName}>{story.name}</Text>
                      <Text style={styles.storyDuration}>{story.duration}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              )}
            </Card>

            <Card style={styles.infoCard}>
              <View style={styles.infoHeader}>
                <Ionicons name="information-circle" size={20} color={COLORS.textSecondary} />
                <Text style={styles.infoTitle}>How It Works</Text>
              </View>
              <Text style={styles.infoText}>
                NAO will narrate the story using text-to-speech and perform gestures to bring the story to life. Make sure your story audio files are in the stories folder on your laptop.
              </Text>
            </Card>
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  scrollView: { flex: 1 },
  scrollContent: { padding: SPACING.md, paddingBottom: SPACING.xxl },
  header: { flexDirection: 'row', alignItems: 'center', marginBottom: SPACING.lg, gap: SPACING.sm },
  headerTitle: { fontSize: FONT_SIZES.xxl, fontWeight: 'bold', color: COLORS.text },
  warningCard: { backgroundColor: COLORS.warning + '20', borderColor: COLORS.warning, borderWidth: 1, marginBottom: SPACING.md },
  warningContent: { flexDirection: 'row', alignItems: 'center', gap: SPACING.sm },
  warningText: { color: COLORS.warning, fontSize: FONT_SIZES.md, flex: 1 },
  tabContainer: { flexDirection: 'row', marginBottom: SPACING.md, backgroundColor: COLORS.surface, borderRadius: BORDER_RADIUS.md, padding: 4 },
  tab: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: SPACING.sm, borderRadius: BORDER_RADIUS.sm, gap: SPACING.xs },
  tabActive: { backgroundColor: COLORS.primary },
  tabText: { fontSize: FONT_SIZES.md, color: COLORS.textMuted },
  tabTextActive: { color: COLORS.text, fontWeight: '600' },
  card: { marginBottom: SPACING.md },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: SPACING.md },
  cardTitleRow: { flexDirection: 'row', alignItems: 'center', gap: SPACING.sm },
  cardTitle: { fontSize: FONT_SIZES.xl, fontWeight: 'bold', color: COLORS.text },
  statusBadge: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: SPACING.sm, paddingVertical: SPACING.xs, borderRadius: BORDER_RADIUS.full, gap: 6 },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  statusText: { fontSize: FONT_SIZES.xs, fontWeight: '600' },
  description: { color: COLORS.textSecondary, fontSize: FONT_SIZES.md, lineHeight: 22, marginBottom: SPACING.md },
  stepsList: { marginBottom: SPACING.lg },
  stepItem: { flexDirection: 'row', alignItems: 'center', marginBottom: SPACING.sm, gap: SPACING.sm },
  stepNumber: { width: 28, height: 28, borderRadius: 14, backgroundColor: COLORS.primary + '30', justifyContent: 'center', alignItems: 'center' },
  stepActive: { backgroundColor: COLORS.success },
  stepNumberText: { color: COLORS.primary, fontSize: FONT_SIZES.sm, fontWeight: 'bold' },
  stepText: { color: COLORS.textSecondary, fontSize: FONT_SIZES.sm, flex: 1 },
  statusDisplay: { backgroundColor: COLORS.surfaceLight, borderRadius: BORDER_RADIUS.md, padding: SPACING.lg, alignItems: 'center', marginBottom: SPACING.lg, borderWidth: 2 },
  statusMessage: { color: COLORS.text, fontSize: FONT_SIZES.md, textAlign: 'center', marginTop: SPACING.sm },
  lastAlert: { color: COLORS.textMuted, fontSize: FONT_SIZES.sm, marginTop: SPACING.xs },
  currentExercise: { color: COLORS.success, fontSize: FONT_SIZES.sm, fontWeight: '600', marginTop: SPACING.xs },
  responseContainer: { backgroundColor: COLORS.warning + '20', borderRadius: BORDER_RADIUS.md, padding: SPACING.md, marginBottom: SPACING.md },
  responsePrompt: { color: COLORS.warning, fontSize: FONT_SIZES.md, fontWeight: '600', textAlign: 'center', marginBottom: SPACING.sm },
  responseButtons: { flexDirection: 'row', justifyContent: 'space-around', gap: SPACING.sm },
  yesButton: { flex: 1, backgroundColor: COLORS.success, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', padding: SPACING.sm, borderRadius: BORDER_RADIUS.md, gap: SPACING.xs },
  noButton: { flex: 1, backgroundColor: COLORS.textMuted, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', padding: SPACING.sm, borderRadius: BORDER_RADIUS.md, gap: SPACING.xs },
  stopResponseButton: { flex: 1, backgroundColor: COLORS.error, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', padding: SPACING.sm, borderRadius: BORDER_RADIUS.md, gap: SPACING.xs },
  responseButtonText: { color: COLORS.text, fontSize: FONT_SIZES.md, fontWeight: '600' },
  buttonRow: { marginBottom: SPACING.md },
  primaryButton: { backgroundColor: COLORS.primary, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', padding: SPACING.md, borderRadius: BORDER_RADIUS.md, gap: SPACING.sm },
  successButton: { backgroundColor: COLORS.success, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', padding: SPACING.md, borderRadius: BORDER_RADIUS.md, gap: SPACING.sm },
  stopButton: { backgroundColor: COLORS.error, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', padding: SPACING.md, borderRadius: BORDER_RADIUS.md, gap: SPACING.sm },
  buttonDisabled: { opacity: 0.5 },
  buttonText: { color: COLORS.text, fontSize: FONT_SIZES.lg, fontWeight: '600' },
  testButton: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', padding: SPACING.md, borderRadius: BORDER_RADIUS.md, borderWidth: 1, borderColor: COLORS.primary, gap: SPACING.sm },
  testButtonText: { color: COLORS.primary, fontSize: FONT_SIZES.md, fontWeight: '600' },
  infoCard: { marginBottom: SPACING.md, backgroundColor: COLORS.surfaceLight },
  infoHeader: { flexDirection: 'row', alignItems: 'center', gap: SPACING.sm, marginBottom: SPACING.sm },
  infoTitle: { color: COLORS.text, fontSize: FONT_SIZES.md, fontWeight: '600' },
  infoText: { color: COLORS.textSecondary, fontSize: FONT_SIZES.sm, lineHeight: 20 },
  // Automation styles
  lightStatusDisplay: { borderRadius: BORDER_RADIUS.lg, padding: SPACING.xl, alignItems: 'center', marginBottom: SPACING.lg, borderWidth: 2, borderColor: COLORS.border },
  lightStatusText: { fontSize: FONT_SIZES.xl, fontWeight: 'bold', marginTop: SPACING.md },
  lastActionText: { color: COLORS.textSecondary, fontSize: FONT_SIZES.sm, marginTop: SPACING.sm, textAlign: 'center' },
  sectionTitle: { color: COLORS.text, fontSize: FONT_SIZES.md, fontWeight: '600', marginBottom: SPACING.sm, marginTop: SPACING.sm },
  voiceDescription: { color: COLORS.textSecondary, fontSize: FONT_SIZES.sm, marginBottom: SPACING.md },
  lightButtonsRow: { flexDirection: 'row', gap: SPACING.md, marginBottom: SPACING.md },
  lightOnButton: { flex: 1, backgroundColor: COLORS.warning, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', padding: SPACING.md, borderRadius: BORDER_RADIUS.md, gap: SPACING.sm },
  lightOffButton: { flex: 1, backgroundColor: COLORS.textMuted, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', padding: SPACING.md, borderRadius: BORDER_RADIUS.md, gap: SPACING.sm },
  voiceOnButton: { flex: 1, backgroundColor: COLORS.success, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', padding: SPACING.md, borderRadius: BORDER_RADIUS.md, gap: SPACING.xs },
  voiceOffButton: { flex: 1, backgroundColor: COLORS.primary, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', padding: SPACING.md, borderRadius: BORDER_RADIUS.md, gap: SPACING.xs },
  voiceButtonText: { color: COLORS.text, fontSize: FONT_SIZES.sm, fontWeight: '600' },
  // IP Input styles
  ipInputRow: { flexDirection: 'row', gap: SPACING.sm, marginBottom: SPACING.lg },
  ipInput: { flex: 1, backgroundColor: COLORS.surfaceLight, borderRadius: BORDER_RADIUS.md, padding: SPACING.md, color: COLORS.text, fontSize: FONT_SIZES.md, borderWidth: 1, borderColor: COLORS.border },
  ipSaveButton: { backgroundColor: COLORS.primary, borderRadius: BORDER_RADIUS.md, paddingHorizontal: SPACING.lg, justifyContent: 'center' },
  ipSaveText: { color: COLORS.text, fontSize: FONT_SIZES.md, fontWeight: '600' },
  // Listen button styles
  listenButton: { backgroundColor: COLORS.secondary, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', padding: SPACING.lg, borderRadius: BORDER_RADIUS.lg, gap: SPACING.md, marginBottom: SPACING.lg },
  listeningActive: { backgroundColor: COLORS.error },
  listenButtonText: { color: COLORS.text, fontSize: FONT_SIZES.md, fontWeight: '600' },
  // Storytelling styles
  storiesGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACING.md },
  storyCard: { width: '47%', backgroundColor: COLORS.surfaceLight, borderRadius: BORDER_RADIUS.lg, padding: SPACING.lg, alignItems: 'center', borderWidth: 1, borderColor: COLORS.border },
  storyIcon: { fontSize: 40, marginBottom: SPACING.sm },
  storyName: { color: COLORS.text, fontSize: FONT_SIZES.sm, fontWeight: '600', textAlign: 'center', marginBottom: SPACING.xs },
  storyDuration: { color: COLORS.textMuted, fontSize: FONT_SIZES.xs },
});
