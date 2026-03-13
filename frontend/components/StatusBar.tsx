import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS, SPACING, FONT_SIZES, BORDER_RADIUS } from '../constants/theme';
import { useRobotStore } from '../store/robotStore';

export function StatusBar() {
  const { status } = useRobotStore();
  
  const getBatteryIcon = () => {
    if (!status?.connected) return 'battery-dead';
    const level = status.battery_level;
    if (level > 75) return 'battery-full';
    if (level > 50) return 'battery-half';
    if (level > 25) return 'battery-half';
    return 'battery-dead';
  };
  
  const getBatteryColor = () => {
    if (!status?.connected) return COLORS.textMuted;
    const level = status.battery_level;
    if (level > 50) return COLORS.success;
    if (level > 25) return COLORS.warning;
    return COLORS.error;
  };
  
  return (
    <View style={styles.container}>
      <View style={styles.statusItem}>
        <Ionicons 
          name={status?.connected ? 'wifi' : 'wifi-outline'} 
          size={18} 
          color={status?.connected ? COLORS.success : COLORS.textMuted} 
        />
        <Text style={[styles.statusText, { color: status?.connected ? COLORS.success : COLORS.textMuted }]}>
          {status?.connected ? 'Connected' : 'Disconnected'}
        </Text>
      </View>
      
      {status?.connected && (
        <>
          <View style={styles.divider} />
          <View style={styles.statusItem}>
            <Ionicons name={getBatteryIcon()} size={18} color={getBatteryColor()} />
            <Text style={[styles.statusText, { color: getBatteryColor() }]}>
              {status.battery_level}%
            </Text>
          </View>
          
          <View style={styles.divider} />
          <View style={styles.statusItem}>
            <Ionicons name="thermometer" size={18} color={COLORS.textSecondary} />
            <Text style={styles.statusText}>{(status.temperature ?? 0).toFixed(1)}°C</Text>
          </View>
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: COLORS.surface,
    paddingVertical: SPACING.sm,
    paddingHorizontal: SPACING.md,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  statusItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACING.xs,
  },
  statusText: {
    color: COLORS.textSecondary,
    fontSize: FONT_SIZES.sm,
    fontWeight: '500',
  },
  divider: {
    width: 1,
    height: 16,
    backgroundColor: COLORS.border,
    marginHorizontal: SPACING.md,
  },
});
