// Theme constants for NAO Robot Control App
export const COLORS = {
  // Primary colors
  background: '#0a0a0f',
  surface: '#12121a',
  surfaceLight: '#1a1a25',
  
  // Accent colors
  primary: '#00a8ff',
  primaryDark: '#0066cc',
  primaryLight: '#4dc3ff',
  
  // Status colors
  success: '#00ff88',
  warning: '#ffaa00',
  error: '#ff4444',
  
  // Text colors
  text: '#ffffff',
  textSecondary: '#8899aa',
  textMuted: '#556677',
  
  // Border colors
  border: '#2a2a3a',
  borderLight: '#3a3a4a',
  
  // Special
  glow: 'rgba(0, 168, 255, 0.3)',
  overlay: 'rgba(0, 0, 0, 0.7)',
};

export const SPACING = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};

export const BORDER_RADIUS = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  full: 999,
};

export const FONT_SIZES = {
  xs: 10,
  sm: 12,
  md: 14,
  lg: 16,
  xl: 20,
  xxl: 24,
  hero: 32,
};

export const SHADOWS = {
  glow: {
    shadowColor: COLORS.primary,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.5,
    shadowRadius: 10,
    elevation: 10,
  },
  card: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 5,
  },
};
