import React, { useEffect, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS, SPACING, FONT_SIZES } from '../../constants/theme';
import { GestureButton } from '../../components/GestureButton';
import { useRobotStore } from '../../store/robotStore';
import { useFocusEffect } from 'expo-router';

export default function ActionsScreen() {
  const { status, gestures, fetchGestures, executeGesture } = useRobotStore();

  useFocusEffect(
    useCallback(() => {
      if (status?.connected && gestures.length === 0) {
        fetchGestures();
      }
    }, [status?.connected, gestures.length])
  );

  const handleGesture = async (gestureName: string) => {
    if (!status?.connected) {
      Alert.alert('Not Connected', 'Please connect to a robot first');
      return;
    }
    try {
      await executeGesture(gestureName);
    } catch (error) {
      Alert.alert('Error', 'Failed to execute gesture');
    }
  };

  if (!status?.connected) {
    return (
      <SafeAreaView style={styles.container} edges={['bottom']}>
        <View style={styles.notConnected}>
          <Ionicons name="hand-left-outline" size={64} color={COLORS.textMuted} />
          <Text style={styles.notConnectedTitle}>Not Connected</Text>
          <Text style={styles.notConnectedText}>
            Please connect to a NAO robot first to trigger gestures and actions.
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <ScrollView style={styles.scrollView} contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <Text style={styles.title}>Gestures & Actions</Text>
          <Text style={styles.subtitle}>Tap to trigger robot animations</Text>
        </View>

        <View style={styles.gestureGrid}>
          {gestures.map((gesture) => (
            <GestureButton
              key={gesture.name}
              name={gesture.name}
              description={gesture.description}
              icon={gesture.icon}
              onPress={() => handleGesture(gesture.name)}
            />
          ))}
        </View>

        {gestures.length === 0 && (
          <View style={styles.loading}>
            <Text style={styles.loadingText}>Loading gestures...</Text>
          </View>
        )}
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
  gestureGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  loading: {
    padding: SPACING.xl,
    alignItems: 'center',
  },
  loadingText: {
    color: COLORS.textSecondary,
    fontSize: FONT_SIZES.md,
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
