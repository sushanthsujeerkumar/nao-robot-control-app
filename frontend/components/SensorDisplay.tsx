import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS, SPACING, BORDER_RADIUS, FONT_SIZES } from '../constants/theme';

interface SensorDisplayProps {
  label: string;
  value: string | number;
  unit?: string;
  icon: string;
  color?: string;
  active?: boolean;
}

export function SensorDisplay({ label, value, unit, icon, color = COLORS.primary, active }: SensorDisplayProps) {
  return (
    <View style={[styles.container, active && { borderColor: color }]}>
      <View style={styles.header}>
        <Ionicons name={icon as any} size={20} color={color} />
        <Text style={styles.label}>{label}</Text>
      </View>
      <View style={styles.valueRow}>
        <Text style={[styles.value, { color }]}>
          {typeof value === 'number' ? value.toFixed(2) : value}
        </Text>
        {unit && <Text style={styles.unit}>{unit}</Text>}
      </View>
      {active !== undefined && (
        <View style={[styles.indicator, { backgroundColor: active ? color : COLORS.textMuted }]} />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: COLORS.surface,
    borderRadius: BORDER_RADIUS.md,
    padding: SPACING.md,
    borderWidth: 1,
    borderColor: COLORS.border,
    minWidth: 100,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACING.xs,
    marginBottom: SPACING.xs,
  },
  label: {
    color: COLORS.textSecondary,
    fontSize: FONT_SIZES.xs,
    textTransform: 'uppercase',
  },
  valueRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: SPACING.xs,
  },
  value: {
    fontSize: FONT_SIZES.xl,
    fontWeight: '700',
    fontFamily: 'monospace',
  },
  unit: {
    color: COLORS.textMuted,
    fontSize: FONT_SIZES.sm,
  },
  indicator: {
    width: 8,
    height: 8,
    borderRadius: 4,
    position: 'absolute',
    top: SPACING.sm,
    right: SPACING.sm,
  },
});
