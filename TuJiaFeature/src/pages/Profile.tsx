import React, { useEffect, useState } from 'react';
import { Card, Form, Input, Button, Radio, Select, Checkbox, Typography, message, Spin } from 'antd';
import { getUserProfile, updateUserProfile, type UserProfile } from '../services/userApi';
import type { UserRole } from '../constants/onboardingOptions';
import {
  ROLE_OPTIONS,
  OPERATOR_LISTING_SCALE,
  OPERATOR_FOCUS,
  EXPERIENCE_LEVEL,
  PRIMARY_CITIES,
  INVESTMENT_STAGE,
  BUDGET_TIER,
  INVESTOR_PRIORITIES,
  HOLD_HORIZON,
  GUEST_TRAVEL_PURPOSE,
  GUEST_PRICE_TIER,
  DISTRICT_OPTIONS,
  FACILITY_OPTIONS,
  ACQUISITION_CHANNEL,
  CONTENT_INTERESTS,
} from '../constants/onboardingOptions';
import { useAuth } from '../context/AuthContext';

const { Title, Paragraph } = Typography;

const maxTwo = (arr: string[]) => (arr || []).slice(0, 2);
const maxThree = (arr: string[]) => (arr || []).slice(0, 3);

function inferGuestPriceTier(min?: number | null, max?: number | null): string {
  if (min == null && max == null) return 'any';
  const m = min ?? undefined;
  const x = max ?? undefined;
  if (x === 200 && m === undefined) return 'lt200';
  if (m === 200 && x === 400) return '200_400';
  if (m === 400 && x === 700) return '400_700';
  if (m === 700 && (x === 50000 || x === 5000)) return 'gt700';
  return 'any';
}

const Profile: React.FC = () => {
  const { refreshUser } = useAuth();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);
  const roleWatch = Form.useWatch('user_role', form);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const p = await getUserProfile();
        if (cancelled) return;
        const pa = (p.persona_answers || {}) as Record<string, unknown>;
        setSummary(p.persona_summary ?? null);
        form.setFieldsValue({
          phone: p.phone,
          full_name: p.full_name,
          email: p.email,
          user_role: (p.user_role as UserRole) || undefined,
          listing_scale: pa.listing_scale,
          primary_city: pa.primary_city,
          operator_focus: pa.operator_focus,
          experience_level: pa.experience_level,
          investment_stage: pa.investment_stage,
          budget_tier: pa.budget_tier,
          investor_priorities: pa.investor_priorities,
          hold_horizon: pa.hold_horizon,
          travel_purpose: p.travel_purpose,
          guest_price_tier: inferGuestPriceTier(p.preferred_price_min, p.preferred_price_max),
          preferred_district: p.preferred_district,
          required_facilities: p.required_facilities,
          acquisition_channel: pa.acquisition_channel,
          content_interests: pa.content_interests,
        });
      } catch {
        message.error('加载个人信息失败');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [form]);

  const onFinish = async (v: Record<string, unknown>) => {
    const role = v.user_role as UserRole | undefined;
    if (!role) {
      message.warning('请选择身份');
      return;
    }
    setSaving(true);
    try {
      const persona: Record<string, unknown> = {
        acquisition_channel: v.acquisition_channel,
        content_interests: maxTwo((v.content_interests as string[]) || []),
      };
      let preferred_district: string | undefined = v.preferred_district as string | undefined;
      let travel_purpose: string | undefined = v.travel_purpose as string | undefined;
      let required_facilities: string[] | undefined = maxThree((v.required_facilities as string[]) || []);
      let preferred_price_min: number | undefined;
      let preferred_price_max: number | undefined;

      if (role === 'operator') {
        persona.listing_scale = v.listing_scale;
        persona.primary_city = v.primary_city;
        persona.operator_focus = maxTwo((v.operator_focus as string[]) || []);
        persona.experience_level = v.experience_level;
      } else if (role === 'investor') {
        persona.investment_stage = v.investment_stage;
        persona.budget_tier = v.budget_tier;
        persona.investor_priorities = maxTwo((v.investor_priorities as string[]) || []);
        persona.hold_horizon = v.hold_horizon;
      } else {
        travel_purpose = v.travel_purpose as string | undefined;
        preferred_district = v.preferred_district as string | undefined;
        required_facilities = maxThree((v.required_facilities as string[]) || []);
        const tier = GUEST_PRICE_TIER.find((t) => t.value === v.guest_price_tier);
        preferred_price_min = tier?.min;
        preferred_price_max = tier?.max;
      }

      const payload: Partial<UserProfile> & Record<string, unknown> = {
        phone: v.phone as string | undefined,
        full_name: v.full_name as string | undefined,
        email: v.email as string | undefined,
        user_role: role,
        persona_answers: persona,
        travel_purpose,
        preferred_district,
        required_facilities,
        preferred_price_min,
        preferred_price_max,
      };

      const updated = await updateUserProfile(payload);
      setSummary(updated.persona_summary ?? null);
      message.success('已保存');
      void refreshUser();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-24">
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <Title level={3} className="!mb-1 font-serif">
          个人信息
        </Title>
        <Paragraph type="secondary" className="!mb-0">
          修改后将自动更新用户画像摘要，并用于个性化推荐。
        </Paragraph>
      </div>

      <Card title="用户画像摘要" className="border-[#ebe7e0]">
        <Paragraph className="!mb-0 whitespace-pre-wrap text-[#4a4a4a]">
          {summary || '暂无摘要，请完善下方问卷后保存。'}
        </Paragraph>
      </Card>

      <Card title="基本资料" className="border-[#ebe7e0]">
        <Form form={form} layout="vertical" onFinish={onFinish}>
          <Form.Item name="full_name" label="昵称 / 姓名">
            <Input placeholder="选填" />
          </Form.Item>
          <Form.Item name="phone" label="手机号">
            <Input placeholder="选填" />
          </Form.Item>
          <Form.Item name="email" label="邮箱">
            <Input placeholder="选填" />
          </Form.Item>

          <Title level={5}>身份与调研</Title>
          <Form.Item name="user_role" label="您的身份" rules={[{ required: true, message: '请选择' }]}>
            <Radio.Group options={ROLE_OPTIONS} />
          </Form.Item>

          {roleWatch === 'operator' && (
            <>
              <Form.Item name="listing_scale" label="房源规模" rules={[{ required: true, message: '请选择' }]}>
                <Radio.Group options={OPERATOR_LISTING_SCALE} />
              </Form.Item>
              <Form.Item name="primary_city" label="主要城市/区域" rules={[{ required: true, message: '请选择' }]}>
                <Select options={PRIMARY_CITIES.map((c) => ({ value: c, label: c }))} placeholder="请选择" />
              </Form.Item>
              <Form.Item
                name="operator_focus"
                label="优先功能（最多 2 项）"
                rules={[
                  { required: true, message: '请至少选一项' },
                  {
                    validator: (_: unknown, val: string[]) =>
                      val && val.length > 2 ? Promise.reject(new Error('最多 2 项')) : Promise.resolve(),
                  },
                ]}
              >
                <Checkbox.Group options={OPERATOR_FOCUS} />
              </Form.Item>
              <Form.Item name="experience_level" label="运营经验" rules={[{ required: true, message: '请选择' }]}>
                <Radio.Group options={EXPERIENCE_LEVEL} />
              </Form.Item>
            </>
          )}

          {roleWatch === 'investor' && (
            <>
              <Form.Item name="investment_stage" label="投资阶段" rules={[{ required: true, message: '请选择' }]}>
                <Radio.Group options={INVESTMENT_STAGE} />
              </Form.Item>
              <Form.Item name="budget_tier" label="预算区间" rules={[{ required: true, message: '请选择' }]}>
                <Radio.Group options={BUDGET_TIER} />
              </Form.Item>
              <Form.Item
                name="investor_priorities"
                label="看重指标（最多 2 项）"
                rules={[
                  { required: true, message: '请至少选一项' },
                  {
                    validator: (_: unknown, val: string[]) =>
                      val && val.length > 2 ? Promise.reject(new Error('最多 2 项')) : Promise.resolve(),
                  },
                ]}
              >
                <Checkbox.Group options={INVESTOR_PRIORITIES} />
              </Form.Item>
              <Form.Item name="hold_horizon" label="持有周期" rules={[{ required: true, message: '请选择' }]}>
                <Radio.Group options={HOLD_HORIZON} />
              </Form.Item>
            </>
          )}

          {roleWatch === 'guest' && (
            <>
              <Form.Item
                name="travel_purpose"
                label="关注的房源场景（用于推荐，非预订）"
                rules={[{ required: true, message: '请选择' }]}
              >
                <Radio.Group options={GUEST_TRAVEL_PURPOSE} />
              </Form.Item>
              <Form.Item
                name="guest_price_tier"
                label="价格带（每晚）"
                rules={[{ required: true, message: '请选择' }]}
              >
                <Radio.Group>
                  {GUEST_PRICE_TIER.map((t) => (
                    <Radio key={t.value} value={t.value}>
                      {t.label}
                    </Radio>
                  ))}
                </Radio.Group>
              </Form.Item>
              <Form.Item name="preferred_district" label="偏好区域" rules={[{ required: true, message: '请选择' }]}>
                <Select options={DISTRICT_OPTIONS.map((d) => ({ value: d, label: d }))} placeholder="请选择" />
              </Form.Item>
              <Form.Item
                name="required_facilities"
                label="必带设施（最多 3 项）"
                rules={[
                  {
                    validator: (_: unknown, val: string[]) =>
                      val && val.length > 3 ? Promise.reject(new Error('最多 3 项')) : Promise.resolve(),
                  },
                ]}
              >
                <Checkbox.Group options={FACILITY_OPTIONS.map((f) => ({ value: f, label: f }))} />
              </Form.Item>
            </>
          )}

          <Form.Item name="acquisition_channel" label="了解渠道（选填）">
            <Radio.Group options={ACQUISITION_CHANNEL} />
          </Form.Item>
          <Form.Item name="content_interests" label="希望接收的内容（最多 2 项，选填）">
            <Checkbox.Group options={CONTENT_INTERESTS} />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={saving} size="large">
              保存
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default Profile;
