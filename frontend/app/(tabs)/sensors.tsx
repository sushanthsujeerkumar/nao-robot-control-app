import React, { useEffect, useCallback, useRef, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Image } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS, SPACING, BORDER_RADIUS, FONT_SIZES } from '../../constants/theme';
import { Card } from '../../components/Card';
import { SensorDisplay } from '../../components/SensorDisplay';
import { useRobotStore } from '../../store/robotStore';
import { useFocusEffect } from 'expo-router';
import axios from 'axios';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL + '/api';

export default function SensorsScreen() {
  const { status, sensors, fetchSensors } = useRobotStore();
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const [cameraFrame, setCameraFrame] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      if (status?.connected) {
        // Initial fetch
        fetchSensors();
        fetchCameraFrame();

        // Set up polling for sensors
        intervalRef.current = setInterval(() => {
          fetchSensors();
          fetchCameraFrame();
        }, 1000);
      }

      return () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      };
    }, [status?.connected])
  );

  const fetchCameraFrame = async () => {
    try {
      const response = await axios.get(`${API_URL}/robot/camera/frame`);
      setCameraFrame(response.data.frame);
    } catch (error) {
      console.log('Error fetching camera frame');
    }
  };

  if (!status?.connected) {
    return (
      <SafeAreaView style={styles.container} edges={['bottom']}>
        <View style={styles.notConnected}>
          <Ionicons name="analytics-outline" size={64} color={COLORS.textMuted} />
          <Text style={styles.notConnectedTitle}>Not Connected</Text>
          <Text style={styles.notConnectedText}>
            Please connect to a NAO robot first to view sensor data.
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <ScrollView style={styles.scrollView} contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <Text style={styles.title}>Sensor Monitor</Text>
          <Text style={styles.subtitle}>Real-time robot sensor data</Text>
        </View>

        {/* Camera Feed */}
        <Card title="Camera Feed" style={styles.cameraCard}>
          <View style={styles.cameraContainer}>
            {cameraFrame ? (
              <Image source={{ uri: cameraFrame }} style={styles.cameraImage} />
            ) : (
              <View style={styles.cameraPlaceholder}>
                <Ionicons name="camera" size={32} color={COLORS.textMuted} />
                <Text style={styles.cameraText}>Loading camera...</Text>
              </View>
            )}
          </View>
        </Card>

        {/* Battery & Temperature */}
        <Card title="System Status" style={styles.sectionCard}>
          <View style={styles.sensorRow}>
            <SensorDisplay
              label="Battery"
              value={sensors?.battery_level || 0}
              unit="%"
              icon="battery-charging"
              color={sensors?.battery_level && sensors.battery_level > 50 ? COLORS.success : COLORS.warning}
            />
            <SensorDisplay
              label="CPU Temp"
              value={sensors?.temperature_cpu || 0}
              unit="°C"
              icon="thermometer"
              color={sensors?.temperature_cpu && sensors.temperature_cpu > 50 ? COLORS.warning : COLORS.primary}
            />
          </View>
          <View style={styles.sensorRow}>
            <SensorDisplay
              label="Batt Temp"
              value={sensors?.temperature_battery || 0}
              unit="°C"
              icon="thermometer-outline"
              color={COLORS.primary}
            />
          </View>
        </Card>

        {/* Touch Sensors */}
        <Card title="Touch Sensors" style={styles.sectionCard}>
          <View style={styles.touchGrid}>
            <View style={styles.touchRow}>
              <SensorDisplay
                label="Head Front"
                value={sensors?.head_touch_front ? 'ON' : 'OFF'}
                icon="hand-left"
                color={sensors?.head_touch_front ? COLORS.success : COLORS.textMuted}
                active={sensors?.head_touch_front}
              />
              <SensorDisplay
                label="Head Middle"
                value={sensors?.head_touch_middle ? 'ON' : 'OFF'}
                icon="hand-left"
                color={sensors?.head_touch_middle ? COLORS.success : COLORS.textMuted}
                active={sensors?.head_touch_middle}
              />
              <SensorDisplay
                label="Head Rear"
                value={sensors?.head_touch_rear ? 'ON' : 'OFF'}
                icon="hand-left"
                color={sensors?.head_touch_rear ? COLORS.success : COLORS.textMuted}
                active={sensors?.head_touch_rear}
              />
            </View>
            <View style={styles.touchRow}>
              <SensorDisplay
                label="Left Hand"
                value={sensors?.left_hand_touch ? 'ON' : 'OFF'}
                icon="hand-left-outline"
                color={sensors?.left_hand_touch ? COLORS.success : COLORS.textMuted}
                active={sensors?.left_hand_touch}
              />
              <SensorDisplay
                label="Right Hand"
                value={sensors?.right_hand_touch ? 'ON' : 'OFF'}
                icon="hand-right-outline"
                color={sensors?.right_hand_touch ? COLORS.success : COLORS.textMuted}
                active={sensors?.right_hand_touch}
              />
            </View>
          </View>
        </Card>

        {/* Sonar Sensors */}
        <Card title="Distance Sensors" style={styles.sectionCard}>
          <View style={styles.sensorRow}>
            <SensorDisplay
              label="Sonar Left"
              value={sensors?.sonar_left || 0}
              unit="m"
              icon="radio"
              color={COLORS.primary}
            />
            <SensorDisplay
              label="Sonar Right"
              value={sensors?.sonar_right || 0}
              unit="m"
              icon="radio"
              color={COLORS.primary}
            />
          </View>
        </Card>

        {/* Joint Angles */}
        <Card title="Joint Angles" style={styles.sectionCard}>
          <View style={styles.sensorRow}>
            <SensorDisplay
              label="Head Yaw"
              value={sensors?.head_yaw || 0}
              unit="rad"
              icon="sync"
              color={COLORS.primaryLight}
            />
            <SensorDisplay
              label="Head Pitch"
              value={sensors?.head_pitch || 0}
              unit="rad"
              icon="swap-vertical"
              color={COLORS.primaryLight}
            />
          </View>
          <View style={styles.sensorRow}>
            <SensorDisplay
              label="L Shoulder"
              value={sensors?.left_shoulder_pitch || 0}
              unit="rad"
              icon="body"
              color={COLORS.primaryLight}
            />
            <SensorDisplay
              label="R Shoulder"
              value={sensors?.right_shoulder_pitch || 0}
              unit="rad"
              icon="body"
              color={COLORS.primaryLight}
            />
          </View>
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  scrollView: {
    flex: 1,
  },
  content: {
    padding: SPACING.md,
    paddingBottom: SPACING.xxl,
  },
  header: {
    alignItems: 'center',
    marginBottom: SPACING.lg,
  },
  title: {
    fontSize: FONT_SIZES.xxl,
    fontWeight: '700',
    color: COLORS.text,
  },
  subtitle: {
    fontSize: FONT_SIZES.md,
    color: COLORS.textSecondary,
    marginTop: SPACING.xs,
  },
  cameraCard: {
    marginBottom: SPACING.md,
  },
  cameraContainer: {
    borderRadius: BORDER_RADIUS.md,
    overflow: 'hidden',
    backgroundColor: COLORS.surfaceLight,
  },
  cameraImage: {
    width: '100%',
    height: 200,
    resizeMode: 'contain',
  },
  cameraPlaceholder: {
    height: 200,
    justifyContent: 'center',
    alignItems: 'center',
  },
  cameraText: {
    color: COLORS.textMuted,
    marginTop: SPACING.sm,
    fontSize: FONT_SIZES.sm,
  },
  sectionCard: {
    marginBottom: SPACING.md,
  },
  sensorRow: {
    flexDirection: 'row',
    gap: SPACING.sm,
    marginBottom: SPACING.sm,
  },
  touchGrid: {
    gap: SPACING.sm,
  },
  touchRow: {
    flexDirection: 'row',
    gap: SPACING.sm,
  },
  notConnected: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: SPACING.xl,
  },
  notConnectedTitle: {
    fontSize: FONT_SIZES.xl,
    fontWeight: '700',
    color: COLORS.text,
    marginTop: SPACING.lg,
  },
  notConnectedText: {
    fontSize: FONT_SIZES.md,
    color: COLORS.textSecondary,
    textAlign: 'center',
    marginTop: SPACING.sm,
  },
});
