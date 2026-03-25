import { apiClient } from '../config/api';
import type { UserRole } from '../constants/onboardingOptions';

export interface OnboardingCompletePayload {
  user_role: UserRole;
  persona_answers: Record<string, unknown>;
  preferred_district?: string;
  travel_purpose?: string;
  required_facilities?: string[];
  preferred_price_min?: number;
  preferred_price_max?: number;
}

export const completeOnboarding = async (
  payload: OnboardingCompletePayload
): Promise<unknown> => {
  const res = await apiClient.post('/api/user/me/onboarding', payload);
  return res.data;
};

export const skipOnboarding = async (userRole?: UserRole): Promise<unknown> => {
  const res = await apiClient.post('/api/user/me/onboarding/skip', null, {
    params: userRole ? { user_role: userRole } : {},
  });
  return res.data;
};
