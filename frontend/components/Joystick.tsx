import React, { useRef, useState } from 'react';
import { View, StyleSheet, PanResponder, Animated, Text } from 'react-native';
import { COLORS, SPACING, BORDER_RADIUS } from '../constants/theme';

interface JoystickProps {
  size?: number;
  onMove: (x: number, y: number) => void;
  onRelease: () => void;
}

export function Joystick({ size = 150, onMove, onRelease }: JoystickProps) {
  const pan = useRef(new Animated.ValueXY()).current;
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const maxDistance = (size / 2) - 25;
  
  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      onPanResponderGrant: () => {
        pan.setOffset({
          x: 0,
          y: 0
        });
      },
      onPanResponderMove: (_, gesture) => {
        let { dx, dy } = gesture;
        
        // Limit to circular boundary
        const distance = Math.sqrt(dx * dx + dy * dy);
        if (distance > maxDistance) {
          dx = (dx / distance) * maxDistance;
          dy = (dy / distance) * maxDistance;
        }
        
        pan.setValue({ x: dx, y: dy });
        
        // Normalize to -1 to 1 range
        const normalizedX = dx / maxDistance;
        const normalizedY = -dy / maxDistance; // Invert Y for forward/backward
        
        setPosition({ x: normalizedX, y: normalizedY });
        onMove(normalizedY, 0, normalizedX); // y is forward/back, x is rotation
      },
      onPanResponderRelease: () => {
        Animated.spring(pan, {
          toValue: { x: 0, y: 0 },
          useNativeDriver: false,
          friction: 5,
        }).start();
        setPosition({ x: 0, y: 0 });
        onRelease();
      },
    })
  ).current;
  
  return (
    <View style={styles.container}>
      <View style={[styles.base, { width: size, height: size, borderRadius: size / 2 }]}>
        <View style={styles.innerRing} />
        <Animated.View
          style={[
            styles.knob,
            {
              transform: [
                { translateX: pan.x },
                { translateY: pan.y },
              ],
            },
          ]}
          {...panResponder.panHandlers}
        />
      </View>
      <View style={styles.valueContainer}>
        <Text style={styles.valueText}>X: {position.x.toFixed(2)}</Text>
        <Text style={styles.valueText}>Y: {position.y.toFixed(2)}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
  },
  base: {
    backgroundColor: COLORS.surface,
    borderWidth: 3,
    borderColor: COLORS.primary,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: COLORS.primary,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.5,
    shadowRadius: 15,
    elevation: 10,
  },
  innerRing: {
    position: 'absolute',
    width: '60%',
    height: '60%',
    borderRadius: 999,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderStyle: 'dashed',
  },
  knob: {
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: COLORS.primary,
    shadowColor: COLORS.primary,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.8,
    shadowRadius: 10,
    elevation: 15,
  },
  valueContainer: {
    flexDirection: 'row',
    marginTop: SPACING.md,
    gap: SPACING.lg,
  },
  valueText: {
    color: COLORS.textSecondary,
    fontSize: 12,
    fontFamily: 'monospace',
  },
});
