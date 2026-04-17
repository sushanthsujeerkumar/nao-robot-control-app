import React, { useState } from 'react';
import { TouchableOpacity, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS, SPACING, BORDER_RADIUS, FONT_SIZES } from '../constants/theme';

interface GestureButtonProps {
  name: string;
  description: string;
  icon: string;
  onPress: () => Promise<void>;
}

const ICON_MAP: { [key: string]: string } = {
  // Gestures
  'hand-left': 'hand-left',
  'body': 'body',
  'checkmark-circle': 'checkmark-circle',
  'close-circle': 'close-circle',
  'musical-notes': 'musical-notes',
  'happy': 'happy',
  'hand-right': 'hand-right',
  'bulb': 'bulb',
  'sad': 'sad',
  'flame': 'flame',
  'alert': 'alert-circle',
  'thumbs-up': 'thumbs-up',
  'flash': 'flash',
  'fitness': 'fitness',
  'arrow-up': 'arrow-up-circle',
  'arrow-down': 'arrow-down-circle',
  'chevron-down': 'chevron-down-circle',
  'arrow-back': 'arrow-back-circle',
  'arrow-forward': 'arrow-forward-circle',
  'caret-up': 'caret-up-circle',
  'caret-down': 'caret-down-circle',
  // Fallbacks
  'hand-wave': 'hand-left',
  'seat': 'bed',
  'human': 'body',
  'human-greeting': 'happy',
  'music': 'musical-notes',
  'handshake': 'people',
  'check': 'checkmark-circle',
  'close': 'close-circle',
  'brain': 'bulb',
  'party-popper': 'sparkles',
};

export function GestureButton({ name, description, icon, onPress }: GestureButtonProps) {
  const [loading, setLoading] = useState(false);
  const [executed, setExecuted] = useState(false);
  
  const handlePress = async () => {
    setLoading(true);
    try {
      await onPress();
      setExecuted(true);
      setTimeout(() => setExecuted(false), 2000);
    } finally {
      setLoading(false);
    }
  };
  
  const ioniconsName = ICON_MAP[icon] || 'radio-button-on';
  
  return (
    <TouchableOpacity 
      style={[styles.button, executed && styles.executed]}
      onPress={handlePress}
      disabled={loading}
      activeOpacity={0.7}
    >
      {loading ? (
        <ActivityIndicator color={COLORS.primary} size="small" />
      ) : (
        <Ionicons 
          name={ioniconsName as any} 
          size={28} 
          color={executed ? COLORS.success : COLORS.primary} 
        />
      )}
      <Text style={[styles.text, executed && styles.executedText]}>{description}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  button: {
    backgroundColor: COLORS.surface,
    borderRadius: BORDER_RADIUS.lg,
    padding: SPACING.md,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: COLORS.border,
    minHeight: 100,
    width: '48%',
    marginBottom: SPACING.md,
  },
  executed: {
    borderColor: COLORS.success,
    backgroundColor: 'rgba(0, 255, 136, 0.1)',
  },
  text: {
    color: COLORS.text,
    fontSize: FONT_SIZES.sm,
    fontWeight: '500',
    marginTop: SPACING.sm,
    textAlign: 'center',
  },
  executedText: {
    color: COLORS.success,
  },
});
