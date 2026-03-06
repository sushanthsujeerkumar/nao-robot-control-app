import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS, SPACING, BORDER_RADIUS, FONT_SIZES } from '../../constants/theme';
import { Card } from '../../components/Card';
import { Button } from '../../components/Button';
import { useRobotStore } from '../../store/robotStore';

const QUICK_PHRASES = [
  'Hello, I am NAO',
  'Nice to meet you',
  'How can I help you?',
  'That is very interesting',
  'Thank you very much',
  'Goodbye!',
];

export default function SpeechScreen() {
  const { status, robotUrl, speak } = useRobotStore();
  const [text, setText] = useState('');
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [history, setHistory] = useState<string[]>([]);

  const handleSpeak = async (speechText: string) => {
    if (!status?.connected || !robotUrl) {
      Alert.alert('Not Connected', 'Please connect to a robot first');
      return;
    }

    if (!speechText.trim()) {
      Alert.alert('Error', 'Please enter some text to speak');
      return;
    }

    setIsSpeaking(true);
    try {
      await speak(speechText);
      // Add to history
      setHistory((prev) => [speechText, ...prev.slice(0, 9)]);
      setText('');
    } catch (error) {
      Alert.alert('Error', 'Failed to speak');
    } finally {
      setIsSpeaking(false);
    }
  };

  if (!status?.connected || !robotUrl) {
    return (
      <SafeAreaView style={styles.container} edges={['bottom']}>
        <View style={styles.notConnected}>
          <Ionicons name="mic-off-outline" size={64} color={COLORS.textMuted} />
          <Text style={styles.notConnectedTitle}>Not Connected</Text>
          <Text style={styles.notConnectedText}>
            Please connect to a NAO robot first to use text-to-speech.
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}
      >
        <ScrollView style={styles.scrollView} contentContainerStyle={styles.content}>
          <View style={styles.header}>
            <Text style={styles.title}>Speech Control</Text>
            <Text style={styles.subtitle}>Make NAO speak any text</Text>
          </View>

          {/* Speech Input */}
          <Card title="Text to Speech">
            <TextInput
              style={styles.textInput}
              value={text}
              onChangeText={setText}
              placeholder="Enter text for NAO to speak..."
              placeholderTextColor={COLORS.textMuted}
              multiline
              numberOfLines={4}
              textAlignVertical="top"
            />
            <Button
              title={isSpeaking ? 'Speaking...' : 'Speak'}
              onPress={() => handleSpeak(text)}
              loading={isSpeaking}
              disabled={!text.trim()}
              icon={<Ionicons name="volume-high" size={20} color="#000" />}
              style={{ marginTop: SPACING.md }}
            />
          </Card>

          {/* Quick Phrases */}
          <Card title="Quick Phrases" style={{ marginTop: SPACING.md }}>
            <View style={styles.phrases}>
              {QUICK_PHRASES.map((phrase, index) => (
                <Button
                  key={index}
                  title={phrase}
                  onPress={() => handleSpeak(phrase)}
                  variant="secondary"
                  size="small"
                  style={styles.phraseBtn}
                />
              ))}
            </View>
          </Card>

          {/* History */}
          {history.length > 0 && (
            <Card title="Recent" style={{ marginTop: SPACING.md }}>
              {history.map((item, index) => (
                <View key={index} style={styles.historyItem}>
                  <Ionicons name="chatbubble-outline" size={16} color={COLORS.textMuted} />
                  <Text
                    style={styles.historyText}
                    numberOfLines={1}
                    onPress={() => handleSpeak(item)}
                  >
                    {item}
                  </Text>
                </View>
              ))}
            </Card>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
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
  textInput: {
    backgroundColor: COLORS.surfaceLight,
    borderRadius: BORDER_RADIUS.md,
    padding: SPACING.md,
    color: COLORS.text,
    fontSize: FONT_SIZES.md,
    minHeight: 120,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  phrases: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: SPACING.sm,
  },
  phraseBtn: {
    marginBottom: SPACING.xs,
  },
  historyItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACING.sm,
    paddingVertical: SPACING.sm,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  historyText: {
    color: COLORS.textSecondary,
    fontSize: FONT_SIZES.sm,
    flex: 1,
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
