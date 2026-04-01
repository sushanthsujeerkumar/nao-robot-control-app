import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS, SPACING, BORDER_RADIUS, FONT_SIZES } from '../../constants/theme';
import { useRobotStore } from '../../store/robotStore';
import { Card } from '../../components/Card';
import axios from 'axios';

type FallDetectionStatus = 'idle' | 'monitoring' | 'person_detected' | 'checking' | 'alert_sent' | 'error';

interface FallDetectionState {
  status: FallDetectionStatus;
  message: string;
  lastAlert?: string;
  personHorizontalSince?: number;
}

export default function FunctionsScreen() {
  const { robotUrl, status } = useRobotStore();
  const [fallDetection, setFallDetection] = useState<FallDetectionState>({
    status: 'idle',
    message: 'Fall detection is not active',
  });
  const [isLoading, setIsLoading] = useState(false);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  const isConnected = status?.connected && robotUrl;

  // Polling for fall detection status
  useEffect(() => {
    if (fallDetection.status === 'monitoring' || fallDetection.status === 'person_detected' || fallDetection.status === 'checking') {
      pollingRef.current = setInterval(async () => {
        try {
          const response = await axios.get(`${robotUrl}/api/robot/fall_detection/status`, { timeout: 5000 });
          if (response.data) {
            setFallDetection({
              status: response.data.status || 'monitoring',
              message: response.data.message || 'Monitoring...',
              lastAlert: response.data.last_alert,
              personHorizontalSince: response.data.person_horizontal_since,
            });
          }
        } catch (error) {
          // Silent error during polling
        }
      }, 2000);
    }

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [fallDetection.status, robotUrl]);

  const startFallDetection = async () => {
    if (!robotUrl) {
      Alert.alert('Not Connected', 'Please connect to NAO robot first.');
      return;
    }

    setIsLoading(true);
    try {
      const response = await axios.post(`${robotUrl}/api/robot/fall_detection/start`, {}, { timeout: 10000 });
      if (response.data.success) {
        setFallDetection({
          status: 'monitoring',
          message: 'Fall detection is now active. Monitoring for fallen persons...',
        });
      } else {
        Alert.alert('Error', response.data.message || 'Failed to start fall detection');
      }
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Failed to start fall detection');
    } finally {
      setIsLoading(false);
    }
  };

  const stopFallDetection = async () => {
    if (!robotUrl) return;

    setIsLoading(true);
    try {
      const response = await axios.post(`${robotUrl}/api/robot/fall_detection/stop`, {}, { timeout: 10000 });
      setFallDetection({
        status: 'idle',
        message: 'Fall detection stopped',
      });
    } catch (error: any) {
      // Still stop locally even if API fails
      setFallDetection({
        status: 'idle',
        message: 'Fall detection stopped',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const testAlert = async () => {
    if (!robotUrl) {
      Alert.alert('Not Connected', 'Please connect to NAO robot first.');
      return;
    }

    setIsLoading(true);
    try {
      const response = await axios.post(`${robotUrl}/api/robot/fall_detection/test`, {}, { timeout: 30000 });
      if (response.data.success) {
        Alert.alert('Test Complete', response.data.message || 'Test alert sent successfully!');
      } else {
        Alert.alert('Test Failed', response.data.message || 'Failed to send test alert');
      }
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Failed to run test');
    } finally {
      setIsLoading(false);
    }
  };

  const getStatusIcon = () => {
    switch (fallDetection.status) {
      case 'monitoring':
        return 'eye';
      case 'person_detected':
        return 'warning';
      case 'checking':
        return 'mic';
      case 'alert_sent':
        return 'mail';
      case 'error':
        return 'alert-circle';
      default:
        return 'shield-outline';
    }
  };

  const getStatusColor = () => {
    switch (fallDetection.status) {
      case 'monitoring':
        return COLORS.primary;
      case 'person_detected':
        return COLORS.warning;
      case 'checking':
        return COLORS.warning;
      case 'alert_sent':
        return COLORS.error;
      case 'error':
        return COLORS.error;
      default:
        return COLORS.textMuted;
    }
  };

  const isActive = fallDetection.status !== 'idle' && fallDetection.status !== 'error';

  return (
    <SafeAreaView style={styles.container} edges={['left', 'right']}>
      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <Ionicons name="shield-checkmark" size={32} color={COLORS.primary} />
          <Text style={styles.headerTitle}>Safety Functions</Text>
        </View>

        {/* Connection Warning */}
        {!isConnected && (
          <Card style={styles.warningCard}>
            <View style={styles.warningContent}>
              <Ionicons name="warning" size={24} color={COLORS.warning} />
              <Text style={styles.warningText}>
                Connect to NAO robot to use safety functions
              </Text>
            </View>
          </Card>
        )}

        {/* Fall Detection Section */}
        <Card style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={styles.cardTitleRow}>
              <Ionicons name="body" size={24} color={COLORS.primary} />
              <Text style={styles.cardTitle}>Fall Detection</Text>
            </View>
            <View style={[styles.statusBadge, { backgroundColor: getStatusColor() + '30' }]}>
              <View style={[styles.statusDot, { backgroundColor: getStatusColor() }]} />
              <Text style={[styles.statusText, { color: getStatusColor() }]}>
                {fallDetection.status === 'idle' ? 'Inactive' : fallDetection.status.replace('_', ' ').toUpperCase()}
              </Text>
            </View>
          </View>

          <Text style={styles.description}>
            Monitors for persons lying horizontal for more than 10-15 seconds. If detected, NAO will:
          </Text>
          
          <View style={styles.stepsList}>
            <View style={styles.stepItem}>
              <View style={styles.stepNumber}><Text style={styles.stepNumberText}>1</Text></View>
              <Text style={styles.stepText}>Move closer and ask "Are you okay?"</Text>
            </View>
            <View style={styles.stepItem}>
              <View style={styles.stepNumber}><Text style={styles.stepNumberText}>2</Text></View>
              <Text style={styles.stepText}>Wait 10 seconds for verbal response</Text>
            </View>
            <View style={styles.stepItem}>
              <View style={styles.stepNumber}><Text style={styles.stepNumberText}>3</Text></View>
              <Text style={styles.stepText}>Play loud alert sound if no response</Text>
            </View>
            <View style={styles.stepItem}>
              <View style={styles.stepNumber}><Text style={styles.stepNumberText}>4</Text></View>
              <Text style={styles.stepText}>Send email alert with photo to caretaker</Text>
            </View>
          </View>

          {/* Status Display */}
          <View style={[styles.statusDisplay, { borderColor: getStatusColor() }]}>
            <Ionicons name={getStatusIcon() as any} size={40} color={getStatusColor()} />
            <Text style={styles.statusMessage}>{fallDetection.message}</Text>
            {fallDetection.lastAlert && (
              <Text style={styles.lastAlert}>Last alert: {fallDetection.lastAlert}</Text>
            )}
          </View>

          {/* Control Buttons */}
          <View style={styles.buttonRow}>
            {!isActive ? (
              <TouchableOpacity
                style={[styles.primaryButton, !isConnected && styles.buttonDisabled]}
                onPress={startFallDetection}
                disabled={!isConnected || isLoading}
              >
                {isLoading ? (
                  <ActivityIndicator color={COLORS.text} />
                ) : (
                  <>
                    <Ionicons name="play" size={20} color={COLORS.text} />
                    <Text style={styles.buttonText}>Start Monitoring</Text>
                  </>
                )}
              </TouchableOpacity>
            ) : (
              <TouchableOpacity
                style={styles.stopButton}
                onPress={stopFallDetection}
                disabled={isLoading}
              >
                {isLoading ? (
                  <ActivityIndicator color={COLORS.text} />
                ) : (
                  <>
                    <Ionicons name="stop" size={20} color={COLORS.text} />
                    <Text style={styles.buttonText}>Stop Monitoring</Text>
                  </>
                )}
              </TouchableOpacity>
            )}
          </View>

          {/* Test Button */}
          <TouchableOpacity
            style={[styles.testButton, !isConnected && styles.buttonDisabled]}
            onPress={testAlert}
            disabled={!isConnected || isLoading}
          >
            <Ionicons name="flask" size={18} color={COLORS.primary} />
            <Text style={styles.testButtonText}>Test Alert System</Text>
          </TouchableOpacity>
        </Card>

        {/* Email Configuration Info */}
        <Card style={styles.infoCard}>
          <View style={styles.infoHeader}>
            <Ionicons name="mail" size={20} color={COLORS.textSecondary} />
            <Text style={styles.infoTitle}>Email Alert Configuration</Text>
          </View>
          <Text style={styles.infoText}>
            Alerts will be sent to: sushanthsujeerkumar@gmail.com
          </Text>
          <Text style={styles.infoSubtext}>
            Configure email settings in the nao.py script on your laptop
          </Text>
        </Card>

        {/* How It Works */}
        <Card style={styles.infoCard}>
          <View style={styles.infoHeader}>
            <Ionicons name="information-circle" size={20} color={COLORS.textSecondary} />
            <Text style={styles.infoTitle}>How It Works</Text>
          </View>
          <Text style={styles.infoText}>
            The NAO robot uses its camera to detect if a person is lying horizontal. 
            Using pose detection, it monitors the person's position and triggers the 
            alert sequence if they remain horizontal for the configured duration.
          </Text>
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
  scrollContent: {
    padding: SPACING.md,
    paddingBottom: SPACING.xxl,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: SPACING.lg,
    gap: SPACING.sm,
  },
  headerTitle: {
    fontSize: FONT_SIZES.xxl,
    fontWeight: 'bold',
    color: COLORS.text,
  },
  warningCard: {
    backgroundColor: COLORS.warning + '20',
    borderColor: COLORS.warning,
    borderWidth: 1,
    marginBottom: SPACING.md,
  },
  warningContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACING.sm,
  },
  warningText: {
    color: COLORS.warning,
    fontSize: FONT_SIZES.md,
    flex: 1,
  },
  card: {
    marginBottom: SPACING.md,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: SPACING.md,
  },
  cardTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACING.sm,
  },
  cardTitle: {
    fontSize: FONT_SIZES.xl,
    fontWeight: 'bold',
    color: COLORS.text,
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: SPACING.sm,
    paddingVertical: SPACING.xs,
    borderRadius: BORDER_RADIUS.full,
    gap: 6,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  statusText: {
    fontSize: FONT_SIZES.xs,
    fontWeight: '600',
  },
  description: {
    color: COLORS.textSecondary,
    fontSize: FONT_SIZES.md,
    lineHeight: 22,
    marginBottom: SPACING.md,
  },
  stepsList: {
    marginBottom: SPACING.lg,
  },
  stepItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: SPACING.sm,
    gap: SPACING.sm,
  },
  stepNumber: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: COLORS.primary + '30',
    justifyContent: 'center',
    alignItems: 'center',
  },
  stepNumberText: {
    color: COLORS.primary,
    fontSize: FONT_SIZES.sm,
    fontWeight: 'bold',
  },
  stepText: {
    color: COLORS.textSecondary,
    fontSize: FONT_SIZES.sm,
    flex: 1,
  },
  statusDisplay: {
    backgroundColor: COLORS.surfaceLight,
    borderRadius: BORDER_RADIUS.md,
    padding: SPACING.lg,
    alignItems: 'center',
    marginBottom: SPACING.lg,
    borderWidth: 2,
  },
  statusMessage: {
    color: COLORS.text,
    fontSize: FONT_SIZES.md,
    textAlign: 'center',
    marginTop: SPACING.sm,
  },
  lastAlert: {
    color: COLORS.textMuted,
    fontSize: FONT_SIZES.sm,
    marginTop: SPACING.xs,
  },
  buttonRow: {
    marginBottom: SPACING.md,
  },
  primaryButton: {
    backgroundColor: COLORS.primary,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: SPACING.md,
    borderRadius: BORDER_RADIUS.md,
    gap: SPACING.sm,
  },
  stopButton: {
    backgroundColor: COLORS.error,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: SPACING.md,
    borderRadius: BORDER_RADIUS.md,
    gap: SPACING.sm,
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  buttonText: {
    color: COLORS.text,
    fontSize: FONT_SIZES.lg,
    fontWeight: '600',
  },
  testButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: SPACING.md,
    borderRadius: BORDER_RADIUS.md,
    borderWidth: 1,
    borderColor: COLORS.primary,
    gap: SPACING.sm,
  },
  testButtonText: {
    color: COLORS.primary,
    fontSize: FONT_SIZES.md,
    fontWeight: '600',
  },
  infoCard: {
    marginBottom: SPACING.md,
    backgroundColor: COLORS.surfaceLight,
  },
  infoHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACING.sm,
    marginBottom: SPACING.sm,
  },
  infoTitle: {
    color: COLORS.text,
    fontSize: FONT_SIZES.md,
    fontWeight: '600',
  },
  infoText: {
    color: COLORS.textSecondary,
    fontSize: FONT_SIZES.sm,
    lineHeight: 20,
  },
  infoSubtext: {
    color: COLORS.textMuted,
    fontSize: FONT_SIZES.xs,
    marginTop: SPACING.xs,
  },
});
