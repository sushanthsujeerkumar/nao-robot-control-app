import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  TouchableOpacity,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS, SPACING, BORDER_RADIUS, FONT_SIZES, SHADOWS } from '../../constants/theme';
import { Card } from '../../components/Card';
import { Button } from '../../components/Button';
import { useRobotStore, RobotConfig } from '../../store/robotStore';

export default function ConnectScreen() {
  const {
    savedRobots,
    status,
    sdkStatus,
    isConnecting,
    connectionError,
    fetchSavedRobots,
    fetchSDKStatus,
    saveRobot,
    deleteRobot,
    connectToRobot,
    disconnectFromRobot,
    setCurrentRobot,
    error,
    clearError,
    clearConnectionError,
  } = useRobotStore();

  const [robotName, setRobotName] = useState('');
  const [ipAddress, setIpAddress] = useState('172.18.16.35');
  const [port, setPort] = useState('9559');
  const [username, setUsername] = useState('nao');
  const [password, setPassword] = useState('nao');
  const [showSaved, setShowSaved] = useState(false);
  const [showErrorModal, setShowErrorModal] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    fetchSavedRobots();
    fetchSDKStatus();
  }, []);

  useEffect(() => {
    if (error) {
      Alert.alert('Error', error);
      clearError();
    }
  }, [error]);

  useEffect(() => {
    if (connectionError) {
      setShowErrorModal(true);
    }
  }, [connectionError]);

  const validateIP = (ip: string) => {
    const regex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
    return regex.test(ip);
  };

  const handleConnect = async () => {
    if (!ipAddress) {
      Alert.alert('Error', 'Please enter an IP address');
      return;
    }
    if (!validateIP(ipAddress)) {
      Alert.alert('Error', 'Please enter a valid IP address');
      return;
    }
    const portNum = parseInt(port) || 9559;
    const result = await connectToRobot(ipAddress, portNum, username, password);
    if (result.success) {
      Alert.alert('Success', 'Connected to NAO robot!');
    }
  };

  const handleSaveRobot = async () => {
    if (!robotName || !ipAddress) {
      Alert.alert('Error', 'Please enter a name and IP address');
      return;
    }
    if (!validateIP(ipAddress)) {
      Alert.alert('Error', 'Please enter a valid IP address');
      return;
    }
    await saveRobot(robotName, ipAddress, parseInt(port) || 9559);
    Alert.alert('Success', 'Robot saved!');
    setRobotName('');
  };

  const handleSelectRobot = async (robot: RobotConfig) => {
    setIpAddress(robot.ip_address);
    setPort(robot.port.toString());
    setRobotName(robot.name);
    setCurrentRobot(robot);
    setShowSaved(false);
  };

  const handleDeleteRobot = (robot: RobotConfig) => {
    Alert.alert(
      'Delete Robot',
      `Are you sure you want to delete ${robot.name}?`,
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Delete', style: 'destructive', onPress: () => deleteRobot(robot.id) },
      ]
    );
  };

  const handleCloseErrorModal = () => {
    setShowErrorModal(false);
    clearConnectionError();
  };

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}
      >
        <ScrollView
          style={styles.scrollView}
          contentContainerStyle={styles.content}
          showsVerticalScrollIndicator={false}
        >
          {/* Header */}
          <View style={styles.header}>
            <View style={styles.robotIcon}>
              <Ionicons name="hardware-chip" size={48} color={COLORS.primary} />
            </View>
            <Text style={styles.title}>Connect to NAO Robot</Text>
            <Text style={styles.subtitle}>
              {status?.connected
                ? `Connected to ${status.robot_name}`
                : 'Enter the robot IP address to connect'}
            </Text>
          </View>

          {/* Connection Method Info */}
          <Card style={styles.infoCard}>
            <View style={styles.infoContent}>
              <Ionicons name="information-circle" size={24} color={COLORS.primary} />
              <View style={styles.infoText}>
                <Text style={styles.infoTitle}>SSH Connection Mode</Text>
                <Text style={styles.infoDesc}>
                  This app connects to your NAO robot via SSH and executes NAOqi commands directly on the robot.
                </Text>
              </View>
            </View>
          </Card>

          {/* Connection Status */}
          {status?.connected && (
            <Card style={styles.statusCard}>
              <View style={styles.connectedInfo}>
                <View style={styles.statusRow}>
                  <View style={styles.statusDot} />
                  <Text style={styles.connectedText}>Connected</Text>
                  {status.connection_mode && (
                    <View style={styles.modeBadge}>
                      <Text style={styles.modeText}>{status.connection_mode}</Text>
                    </View>
                  )}
                </View>
                <Text style={styles.ipText}>{status.ip_address}:9559</Text>
                <View style={styles.statsRow}>
                  <View style={styles.statItem}>
                    <Text style={styles.statValue}>{status.battery_level}%</Text>
                    <Text style={styles.statLabel}>Battery</Text>
                  </View>
                  <View style={styles.statItem}>
                    <Text style={styles.statValue}>{status.posture}</Text>
                    <Text style={styles.statLabel}>Posture</Text>
                  </View>
                  <View style={styles.statItem}>
                    <Text style={styles.statValue}>{Math.floor(status.uptime / 60)}m</Text>
                    <Text style={styles.statLabel}>Uptime</Text>
                  </View>
                </View>
                <Button
                  title="Disconnect"
                  onPress={disconnectFromRobot}
                  variant="danger"
                  size="small"
                  style={{ marginTop: SPACING.md }}
                />
              </View>
            </Card>
          )}

          {/* Connection Form */}
          {!status?.connected && (
            <Card title="Robot Connection">
              <View style={styles.inputGroup}>
                <Text style={styles.label}>Robot Name (optional)</Text>
                <TextInput
                  style={styles.input}
                  value={robotName}
                  onChangeText={setRobotName}
                  placeholder="e.g., NAO Lab"
                  placeholderTextColor={COLORS.textMuted}
                />
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.label}>IP Address *</Text>
                <TextInput
                  style={styles.input}
                  value={ipAddress}
                  onChangeText={setIpAddress}
                  placeholder="172.18.16.35"
                  placeholderTextColor={COLORS.textMuted}
                  keyboardType="numeric"
                  autoCapitalize="none"
                />
                <Text style={styles.hint}>
                  Press NAO's chest button to hear the IP address
                </Text>
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.label}>Port</Text>
                <TextInput
                  style={styles.input}
                  value={port}
                  onChangeText={setPort}
                  placeholder="9559"
                  placeholderTextColor={COLORS.textMuted}
                  keyboardType="numeric"
                />
              </View>

              {/* Advanced Settings Toggle */}
              <TouchableOpacity 
                style={styles.advancedToggle}
                onPress={() => setShowAdvanced(!showAdvanced)}
              >
                <Text style={styles.advancedToggleText}>SSH Credentials</Text>
                <Ionicons 
                  name={showAdvanced ? 'chevron-up' : 'chevron-down'} 
                  size={20} 
                  color={COLORS.textSecondary} 
                />
              </TouchableOpacity>

              {showAdvanced && (
                <>
                  <View style={styles.inputGroup}>
                    <Text style={styles.label}>SSH Username</Text>
                    <TextInput
                      style={styles.input}
                      value={username}
                      onChangeText={setUsername}
                      placeholder="nao"
                      placeholderTextColor={COLORS.textMuted}
                      autoCapitalize="none"
                    />
                  </View>

                  <View style={styles.inputGroup}>
                    <Text style={styles.label}>SSH Password</Text>
                    <TextInput
                      style={styles.input}
                      value={password}
                      onChangeText={setPassword}
                      placeholder="nao"
                      placeholderTextColor={COLORS.textMuted}
                      secureTextEntry
                    />
                    <Text style={styles.hint}>
                      Default credentials: nao / nao
                    </Text>
                  </View>
                </>
              )}

              <View style={styles.buttonRow}>
                <Button
                  title={isConnecting ? 'Connecting...' : 'Connect'}
                  onPress={handleConnect}
                  loading={isConnecting}
                  style={{ flex: 1 }}
                />
                <Button
                  title="Save"
                  onPress={handleSaveRobot}
                  variant="secondary"
                  style={{ flex: 1 }}
                  icon={<Ionicons name="bookmark" size={18} color={COLORS.primary} />}
                />
              </View>
            </Card>
          )}

          {/* Saved Robots */}
          {savedRobots.length > 0 && (
            <Card style={styles.savedCard}>
              <TouchableOpacity
                style={styles.savedHeader}
                onPress={() => setShowSaved(!showSaved)}
              >
                <View style={styles.savedHeaderLeft}>
                  <Ionicons name="list" size={20} color={COLORS.primary} />
                  <Text style={styles.savedTitle}>Saved Robots ({savedRobots.length})</Text>
                </View>
                <Ionicons
                  name={showSaved ? 'chevron-up' : 'chevron-down'}
                  size={20}
                  color={COLORS.textSecondary}
                />
              </TouchableOpacity>

              {showSaved && (
                <View style={styles.robotList}>
                  {savedRobots.map((robot) => (
                    <View key={robot.id} style={styles.robotItem}>
                      <TouchableOpacity
                        style={styles.robotInfo}
                        onPress={() => handleSelectRobot(robot)}
                      >
                        <View style={styles.robotIconSmall}>
                          <Ionicons name="hardware-chip-outline" size={24} color={COLORS.primary} />
                        </View>
                        <View>
                          <Text style={styles.robotName}>{robot.name}</Text>
                          <Text style={styles.robotIP}>
                            {robot.ip_address}:{robot.port}
                          </Text>
                        </View>
                      </TouchableOpacity>
                      <TouchableOpacity
                        style={styles.deleteBtn}
                        onPress={() => handleDeleteRobot(robot)}
                      >
                        <Ionicons name="trash-outline" size={20} color={COLORS.error} />
                      </TouchableOpacity>
                    </View>
                  ))}
                </View>
              )}
            </Card>
          )}

          {/* How to Find IP */}
          <Card title="Troubleshooting" style={styles.helpCard}>
            <View style={styles.helpStep}>
              <Text style={styles.helpNumber}>1</Text>
              <Text style={styles.helpText}>
                Make sure NAO is powered on and connected to WiFi
              </Text>
            </View>
            <View style={styles.helpStep}>
              <Text style={styles.helpNumber}>2</Text>
              <Text style={styles.helpText}>
                Press the chest button once - NAO will say its IP address
              </Text>
            </View>
            <View style={styles.helpStep}>
              <Text style={styles.helpNumber}>3</Text>
              <Text style={styles.helpText}>
                Ensure this server can reach the robot's IP (same network or VPN)
              </Text>
            </View>
            <View style={styles.helpStep}>
              <Text style={styles.helpNumber}>4</Text>
              <Text style={styles.helpText}>
                SSH must be enabled on NAO (port 22) - this is on by default
              </Text>
            </View>
          </Card>
        </ScrollView>
      </KeyboardAvoidingView>

      {/* Connection Error Modal */}
      <Modal
        visible={showErrorModal}
        transparent
        animationType="fade"
        onRequestClose={handleCloseErrorModal}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Ionicons name="close-circle" size={48} color={COLORS.error} />
              <Text style={styles.modalTitle}>Connection Failed</Text>
            </View>
            <Text style={styles.modalMessage}>{connectionError}</Text>
            <Button
              title="OK"
              onPress={handleCloseErrorModal}
              style={{ marginTop: SPACING.lg }}
            />
          </View>
        </View>
      </Modal>
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
    paddingVertical: SPACING.md,
  },
  robotIcon: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: COLORS.surface,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: SPACING.md,
    borderWidth: 2,
    borderColor: COLORS.primary,
    ...SHADOWS.glow,
  },
  title: {
    fontSize: FONT_SIZES.xxl,
    fontWeight: '700',
    color: COLORS.text,
    marginBottom: SPACING.xs,
  },
  subtitle: {
    fontSize: FONT_SIZES.md,
    color: COLORS.textSecondary,
    textAlign: 'center',
  },
  infoCard: {
    marginBottom: SPACING.md,
    borderColor: COLORS.primary,
    backgroundColor: 'rgba(0, 168, 255, 0.1)',
  },
  infoContent: {
    flexDirection: 'row',
    gap: SPACING.md,
  },
  infoText: {
    flex: 1,
  },
  infoTitle: {
    color: COLORS.primary,
    fontSize: FONT_SIZES.md,
    fontWeight: '600',
    marginBottom: SPACING.xs,
  },
  infoDesc: {
    color: COLORS.textSecondary,
    fontSize: FONT_SIZES.sm,
    lineHeight: 20,
  },
  statusCard: {
    marginBottom: SPACING.md,
    borderColor: COLORS.success,
  },
  connectedInfo: {
    alignItems: 'center',
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACING.sm,
    marginBottom: SPACING.xs,
  },
  statusDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: COLORS.success,
  },
  connectedText: {
    color: COLORS.success,
    fontSize: FONT_SIZES.lg,
    fontWeight: '600',
  },
  modeBadge: {
    backgroundColor: COLORS.primary,
    paddingHorizontal: SPACING.sm,
    paddingVertical: 2,
    borderRadius: BORDER_RADIUS.sm,
  },
  modeText: {
    color: '#000',
    fontSize: FONT_SIZES.xs,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  ipText: {
    color: COLORS.textSecondary,
    fontSize: FONT_SIZES.sm,
    marginBottom: SPACING.md,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    width: '100%',
  },
  statItem: {
    alignItems: 'center',
  },
  statValue: {
    color: COLORS.text,
    fontSize: FONT_SIZES.xl,
    fontWeight: '700',
  },
  statLabel: {
    color: COLORS.textSecondary,
    fontSize: FONT_SIZES.xs,
    marginTop: SPACING.xs,
  },
  inputGroup: {
    marginBottom: SPACING.md,
  },
  label: {
    color: COLORS.textSecondary,
    fontSize: FONT_SIZES.sm,
    marginBottom: SPACING.xs,
  },
  input: {
    backgroundColor: COLORS.surfaceLight,
    borderRadius: BORDER_RADIUS.md,
    paddingHorizontal: SPACING.md,
    paddingVertical: SPACING.md,
    color: COLORS.text,
    fontSize: FONT_SIZES.md,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  hint: {
    color: COLORS.textMuted,
    fontSize: FONT_SIZES.xs,
    marginTop: SPACING.xs,
    fontStyle: 'italic',
  },
  advancedToggle: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: SPACING.sm,
    marginBottom: SPACING.md,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
    marginTop: SPACING.sm,
  },
  advancedToggleText: {
    color: COLORS.textSecondary,
    fontSize: FONT_SIZES.sm,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: SPACING.md,
    marginTop: SPACING.sm,
  },
  savedCard: {
    marginTop: SPACING.md,
  },
  savedHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  savedHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACING.sm,
  },
  savedTitle: {
    color: COLORS.text,
    fontSize: FONT_SIZES.md,
    fontWeight: '600',
  },
  robotList: {
    marginTop: SPACING.md,
    gap: SPACING.sm,
  },
  robotItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: COLORS.surfaceLight,
    borderRadius: BORDER_RADIUS.md,
    padding: SPACING.md,
  },
  robotInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACING.md,
    flex: 1,
  },
  robotIconSmall: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: COLORS.surface,
    justifyContent: 'center',
    alignItems: 'center',
  },
  robotName: {
    color: COLORS.text,
    fontSize: FONT_SIZES.md,
    fontWeight: '600',
  },
  robotIP: {
    color: COLORS.textSecondary,
    fontSize: FONT_SIZES.sm,
  },
  deleteBtn: {
    padding: SPACING.sm,
  },
  helpCard: {
    marginTop: SPACING.md,
  },
  helpStep: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: SPACING.md,
    marginBottom: SPACING.md,
  },
  helpNumber: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: COLORS.primary,
    color: '#000',
    fontSize: FONT_SIZES.sm,
    fontWeight: '700',
    textAlign: 'center',
    lineHeight: 24,
  },
  helpText: {
    flex: 1,
    color: COLORS.textSecondary,
    fontSize: FONT_SIZES.sm,
    lineHeight: 20,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: COLORS.overlay,
    justifyContent: 'center',
    alignItems: 'center',
    padding: SPACING.lg,
  },
  modalContent: {
    backgroundColor: COLORS.surface,
    borderRadius: BORDER_RADIUS.lg,
    padding: SPACING.lg,
    width: '100%',
    maxWidth: 400,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  modalHeader: {
    alignItems: 'center',
    marginBottom: SPACING.md,
  },
  modalTitle: {
    color: COLORS.text,
    fontSize: FONT_SIZES.xl,
    fontWeight: '700',
    marginTop: SPACING.sm,
  },
  modalMessage: {
    color: COLORS.textSecondary,
    fontSize: FONT_SIZES.md,
    lineHeight: 22,
    textAlign: 'center',
  },
});
