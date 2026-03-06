import React, { useCallback } from 'react';
import { View, Text, StyleSheet, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS, SPACING, BORDER_RADIUS, FONT_SIZES } from '../../constants/theme';
import { Card } from '../../components/Card';
import { Button } from '../../components/Button';
import { Joystick } from '../../components/Joystick';
import { useRobotStore } from '../../store/robotStore';
import { useFocusEffect } from 'expo-router';

export default function ControlScreen() {
  const { status, robotUrl, sendMoveCommand, stopMovement, fetchStatus } = useRobotStore();

  useFocusEffect(
    useCallback(() => {
      if (status?.connected && robotUrl) {
        fetchStatus();
      }
    }, [status?.connected, robotUrl])
  );

  const handleMove = (x: number, y: number, theta: number) => {
    if (status?.connected && robotUrl) {
      sendMoveCommand(x, y, theta);
    }
  };

  const handleRelease = () => {
    if (status?.connected && robotUrl) {
      stopMovement();
    }
  };

  const handleQuickMove = (direction: string) => {
    if (!status?.connected || !robotUrl) {
      Alert.alert('Not Connected', 'Please connect to a robot first');
      return;
    }

    switch (direction) {
      case 'forward':
        sendMoveCommand(0.5, 0, 0);
        setTimeout(stopMovement, 500);
        break;
      case 'backward':
        sendMoveCommand(-0.5, 0, 0);
        setTimeout(stopMovement, 500);
        break;
      case 'left':
        sendMoveCommand(0, 0, 0.5);
        setTimeout(stopMovement, 500);
        break;
      case 'right':
        sendMoveCommand(0, 0, -0.5);
        setTimeout(stopMovement, 500);
        break;
      case 'stop':
        stopMovement();
        break;
    }
  };

  if (!status?.connected || !robotUrl) {
    return (
      <SafeAreaView style={styles.container} edges={['bottom']}>
        <View style={styles.notConnected}>
          <Ionicons name="wifi-outline" size={64} color={COLORS.textMuted} />
          <Text style={styles.notConnectedTitle}>Not Connected</Text>
          <Text style={styles.notConnectedText}>
            Please connect to a NAO robot first to use movement controls.
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <View style={styles.content}>
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>Movement Control</Text>
          <Text style={styles.subtitle}>Use the joystick to control NAO</Text>
        </View>

        {/* Status Indicator */}
        <View style={styles.statusBadge}>
          <View style={styles.statusDot} />
          <Text style={styles.statusText}>Posture: {status.posture}</Text>
        </View>

        {/* Joystick */}
        <Card style={styles.joystickCard}>
          <Joystick size={180} onMove={handleMove} onRelease={handleRelease} />
        </Card>

        {/* Quick Controls */}
        <Card title="Quick Controls">
          <View style={styles.quickControls}>
            <View style={styles.quickRow}>
              <View style={styles.quickSpacer} />
              <Button
                title=""
                onPress={() => handleQuickMove('forward')}
                style={styles.quickBtn}
                icon={<Ionicons name="arrow-up" size={24} color="#000" />}
              />
              <View style={styles.quickSpacer} />
            </View>
            <View style={styles.quickRow}>
              <Button
                title=""
                onPress={() => handleQuickMove('left')}
                style={styles.quickBtn}
                icon={<Ionicons name="arrow-back" size={24} color="#000" />}
              />
              <Button
                title=""
                onPress={() => handleQuickMove('stop')}
                style={styles.stopBtn}
                variant="danger"
                icon={<Ionicons name="stop" size={24} color="#000" />}
              />
              <Button
                title=""
                onPress={() => handleQuickMove('right')}
                style={styles.quickBtn}
                icon={<Ionicons name="arrow-forward" size={24} color="#000" />}
              />
            </View>
            <View style={styles.quickRow}>
              <View style={styles.quickSpacer} />
              <Button
                title=""
                onPress={() => handleQuickMove('backward')}
                style={styles.quickBtn}
                icon={<Ionicons name="arrow-down" size={24} color="#000" />}
              />
              <View style={styles.quickSpacer} />
            </View>
          </View>
        </Card>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  content: {
    flex: 1,
    padding: SPACING.md,
  },
  header: {
    alignItems: 'center',
    marginBottom: SPACING.md,
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
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: COLORS.surface,
    paddingHorizontal: SPACING.md,
    paddingVertical: SPACING.sm,
    borderRadius: BORDER_RADIUS.full,
    alignSelf: 'center',
    marginBottom: SPACING.md,
    gap: SPACING.sm,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: COLORS.success,
  },
  statusText: {
    color: COLORS.textSecondary,
    fontSize: FONT_SIZES.sm,
  },
  joystickCard: {
    alignItems: 'center',
    paddingVertical: SPACING.xl,
    marginBottom: SPACING.md,
  },
  quickControls: {
    gap: SPACING.sm,
  },
  quickRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: SPACING.sm,
  },
  quickBtn: {
    width: 60,
    height: 60,
    borderRadius: BORDER_RADIUS.md,
  },
  stopBtn: {
    width: 60,
    height: 60,
    borderRadius: BORDER_RADIUS.md,
  },
  quickSpacer: {
    width: 60,
    height: 60,
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
