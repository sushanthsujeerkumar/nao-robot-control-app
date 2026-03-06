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
  Linking,
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
    robotUrl,
    isConnecting,
    connectionError,
    loadSavedRobots,
    saveRobotLocally,
    deleteRobotLocally,
    connectToRobot,
    disconnectFromRobot,
    setCurrentRobot,
    clearConnectionError,
  } = useRobotStore();

  const [robotName, setRobotName] = useState('');
  const [ipAddress, setIpAddress] = useState('172.18.16.35');
  const [port, setPort] = useState('5000');
  const [showSaved, setShowSaved] = useState(false);
  const [showErrorModal, setShowErrorModal] = useState(false);
  const [showSetupModal, setShowSetupModal] = useState(false);

  useEffect(() => {
    loadSavedRobots();
  }, []);

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
    const portNum = parseInt(port) || 5000;
    const result = await connectToRobot(ipAddress, portNum);
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
    saveRobotLocally(robotName, ipAddress, parseInt(port) || 5000);
    Alert.alert('Success', 'Robot saved!');
    setRobotName('');
  };

  const handleSelectRobot = (robot: RobotConfig) => {
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
        { text: 'Delete', style: 'destructive', onPress: () => deleteRobotLocally(robot.id) },
      ]
    );
  };

  const handleCloseErrorModal = () => {
    setShowErrorModal(false);
    clearConnectionError();
  };

  const isConnected = status?.connected && robotUrl;

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
            <View style={[styles.robotIcon, isConnected && styles.robotIconConnected]}>
              <Ionicons 
                name="hardware-chip" 
                size={48} 
                color={isConnected ? COLORS.success : COLORS.primary} 
              />
            </View>
            <Text style={styles.title}>NAO Robot Control</Text>
            <Text style={styles.subtitle}>
              {isConnected
                ? `Connected to ${status.robot_name}`
                : 'Connect directly to your NAO robot'}
            </Text>
          </View>

          {/* Setup Instructions */}
          <TouchableOpacity onPress={() => setShowSetupModal(true)}>
            <Card style={styles.setupCard}>
              <View style={styles.setupContent}>
                <Ionicons name="help-circle" size={24} color={COLORS.primary} />
                <View style={styles.setupText}>
                  <Text style={styles.setupTitle}>First Time Setup Required</Text>
                  <Text style={styles.setupDesc}>
                    Tap here to see how to set up the NAO REST server
                  </Text>
                </View>
                <Ionicons name="chevron-forward" size={20} color={COLORS.textMuted} />
              </View>
            </Card>
          </TouchableOpacity>

          {/* Connection Status */}
          {isConnected && (
            <Card style={styles.statusCard}>
              <View style={styles.connectedInfo}>
                <View style={styles.statusRow}>
                  <View style={styles.statusDot} />
                  <Text style={styles.connectedText}>Connected</Text>
                  <View style={styles.modeBadge}>
                    <Text style={styles.modeText}>Direct</Text>
                  </View>
                </View>
                <Text style={styles.ipText}>{robotUrl}</Text>
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
                    <Text style={styles.statValue}>{status.temperature?.toFixed(0) || '-'}°</Text>
                    <Text style={styles.statLabel}>Temp</Text>
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
          {!isConnected && (
            <Card title="Connect to NAO">
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
                <Text style={styles.label}>NAO IP Address *</Text>
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
                  Press NAO's chest button to hear the IP
                </Text>
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.label}>REST Server Port</Text>
                <TextInput
                  style={styles.input}
                  value={port}
                  onChangeText={setPort}
                  placeholder="5000"
                  placeholderTextColor={COLORS.textMuted}
                  keyboardType="numeric"
                />
                <Text style={styles.hint}>
                  Default: 5000 (set by nao_rest_server.py)
                </Text>
              </View>

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
          {savedRobots.length > 0 && !isConnected && (
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

          {/* Requirements */}
          <Card title="Requirements" style={styles.helpCard}>
            <View style={styles.helpStep}>
              <Ionicons name="checkmark-circle" size={20} color={COLORS.success} />
              <Text style={styles.helpText}>
                Phone connected to same WiFi as NAO robot
              </Text>
            </View>
            <View style={styles.helpStep}>
              <Ionicons name="checkmark-circle" size={20} color={COLORS.success} />
              <Text style={styles.helpText}>
                NAO REST server running on the robot
              </Text>
            </View>
            <View style={styles.helpStep}>
              <Ionicons name="checkmark-circle" size={20} color={COLORS.success} />
              <Text style={styles.helpText}>
                Correct IP address (press chest button)
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

      {/* Setup Instructions Modal */}
      <Modal
        visible={showSetupModal}
        transparent
        animationType="slide"
        onRequestClose={() => setShowSetupModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, styles.setupModalContent]}>
            <View style={styles.modalHeader}>
              <Ionicons name="rocket" size={48} color={COLORS.primary} />
              <Text style={styles.modalTitle}>Setup NAO REST Server</Text>
            </View>
            
            <ScrollView style={styles.setupSteps}>
              <Text style={styles.setupStepTitle}>Step 1: Get the server script</Text>
              <Text style={styles.setupStepText}>
                Download nao_rest_server.py from this app's repository or copy it from your computer.
              </Text>
              
              <Text style={styles.setupStepTitle}>Step 2: Copy to NAO</Text>
              <Text style={styles.setupStepCode}>
                scp nao_rest_server.py nao@{ipAddress || '<NAO_IP>'}:~/
              </Text>
              <Text style={styles.setupStepNote}>Password: nao</Text>
              
              <Text style={styles.setupStepTitle}>Step 3: SSH to NAO</Text>
              <Text style={styles.setupStepCode}>
                ssh nao@{ipAddress || '<NAO_IP>'}
              </Text>
              
              <Text style={styles.setupStepTitle}>Step 4: Run the server</Text>
              <Text style={styles.setupStepCode}>
                python nao_rest_server.py
              </Text>
              
              <Text style={styles.setupStepTitle}>Step 5: Connect from app</Text>
              <Text style={styles.setupStepText}>
                NAO will say "Server ready". Enter the IP in this app and tap Connect!
              </Text>
              
              <View style={styles.setupNote}>
                <Ionicons name="information-circle" size={20} color={COLORS.primary} />
                <Text style={styles.setupNoteText}>
                  The server runs on port 5000 by default. Keep the SSH session open while using the app.
                </Text>
              </View>
            </ScrollView>
            
            <Button
              title="Got it!"
              onPress={() => setShowSetupModal(false)}
              style={{ marginTop: SPACING.md }}
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
  robotIconConnected: {
    borderColor: COLORS.success,
    shadowColor: COLORS.success,
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
  setupCard: {
    marginBottom: SPACING.md,
    borderColor: COLORS.primary,
    backgroundColor: 'rgba(0, 168, 255, 0.05)',
  },
  setupContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACING.md,
  },
  setupText: {
    flex: 1,
  },
  setupTitle: {
    color: COLORS.primary,
    fontSize: FONT_SIZES.md,
    fontWeight: '600',
  },
  setupDesc: {
    color: COLORS.textSecondary,
    fontSize: FONT_SIZES.sm,
    marginTop: 2,
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
    backgroundColor: COLORS.success,
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
    alignItems: 'center',
    gap: SPACING.md,
    marginBottom: SPACING.md,
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
  setupModalContent: {
    maxHeight: '80%',
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
    textAlign: 'center',
  },
  modalMessage: {
    color: COLORS.textSecondary,
    fontSize: FONT_SIZES.md,
    lineHeight: 22,
    textAlign: 'center',
  },
  setupSteps: {
    maxHeight: 400,
  },
  setupStepTitle: {
    color: COLORS.text,
    fontSize: FONT_SIZES.md,
    fontWeight: '600',
    marginTop: SPACING.md,
    marginBottom: SPACING.xs,
  },
  setupStepText: {
    color: COLORS.textSecondary,
    fontSize: FONT_SIZES.sm,
    lineHeight: 20,
  },
  setupStepCode: {
    backgroundColor: COLORS.surfaceLight,
    color: COLORS.primary,
    fontSize: FONT_SIZES.sm,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    padding: SPACING.sm,
    borderRadius: BORDER_RADIUS.sm,
    marginTop: SPACING.xs,
  },
  setupStepNote: {
    color: COLORS.textMuted,
    fontSize: FONT_SIZES.xs,
    marginTop: SPACING.xs,
    fontStyle: 'italic',
  },
  setupNote: {
    flexDirection: 'row',
    gap: SPACING.sm,
    backgroundColor: 'rgba(0, 168, 255, 0.1)',
    padding: SPACING.md,
    borderRadius: BORDER_RADIUS.md,
    marginTop: SPACING.lg,
  },
  setupNoteText: {
    flex: 1,
    color: COLORS.textSecondary,
    fontSize: FONT_SIZES.sm,
    lineHeight: 20,
  },
});
