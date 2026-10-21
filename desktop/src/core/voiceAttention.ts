/** Stateless routing only. Authentication and action approval live elsewhere. */
export type AttentionTranscript = { addressed: boolean; conversational?: boolean; acknowledgement?: boolean; forZae?: boolean; nameRequired?: boolean | null };

export const FOLLOW_UP_MS = 30_000;

export function acceptsVoiceTurn(result: AttentionTranscript, activeConversation: boolean): boolean {
  // forZae: no wake word in use, and ZAE's brain judged the words were meant for her.
  return result.addressed === true || result.forZae === true || (activeConversation && result.conversational === true);
}

export function isQuietVoiceAcknowledgement(result: AttentionTranscript, activeConversation: boolean): boolean {
  return activeConversation && result.acknowledgement === true;
}
