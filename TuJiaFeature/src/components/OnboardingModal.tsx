import React, { useState } from 'react';
import { Modal, Button, Form, Radio, Select, Checkbox, Space, Typography, message } from 'antd';
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
import { completeOnboarding, skipOnboarding } from '../services/onboardingApi';

const { Text, Paragraph } = Typography;

const maxTwo = (arr: string[]) => (arr || []).slice(0, 2);
const maxThree = (arr: string[]) => (arr || []).slice(0, 3);

interface OnboardingModalProps {
  open: boolean;
  user: { username?: string } | null;
  /** 提交或跳过成功后刷新用户信息（父级根据 onboarding_completed 关闭弹窗） */
  onDone: () => void | Promise<void>;
}

const OnboardingModal: React.FC<OnboardingModalProps> = ({ open, user, onDone }) => {
  const [step, setStep] = useState(0);
  const [role, setRole] = useState<UserRole | undefined>();
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm();

  const resetLocal = () => {
    setStep(0);
    setRole(undefined);
    form.resetFields();
  };

  const handleSkip = async () => {
    setSubmitting(true);
    try {
      await skipOnboarding(role);
      message.info('已跳过，稍后可到「个人信息」补充');
      await Promise.resolve(onDone());
      resetLocal();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || '操作失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleFinish = async () => {
    if (!role) {
      message.warning('请选择您的身份');
      return;
    }
    try {
      const v = await form.validateFields();
      setSubmitting(true);

      const persona: Record<string, unknown> = {
        acquisition_channel: v.acquisition_channel,
        content_interests: maxTwo(v.content_interests || []),
      };

      let preferred_district: string | undefined;
      let travel_purpose: string | undefined;
      let required_facilities: string[] | undefined;
      let preferred_price_min: number | undefined;
      let preferred_price_max: number | undefined;

      if (role === 'operator') {
        persona.listing_scale = v.listing_scale;
        persona.primary_city = v.primary_city;
        persona.operator_focus = maxTwo(v.operator_focus || []);
        persona.experience_level = v.experience_level;
      } else if (role === 'investor') {
        persona.investment_stage = v.investment_stage;
        persona.budget_tier = v.budget_tier;
        persona.investor_priorities = maxTwo(v.investor_priorities || []);
        persona.hold_horizon = v.hold_horizon;
      } else {
        travel_purpose = v.travel_purpose;
        preferred_district = v.preferred_district;
        required_facilities = maxThree(v.required_facilities || []);
        const tier = GUEST_PRICE_TIER.find((t) => t.value === v.guest_price_tier);
        preferred_price_min = tier?.min;
        preferred_price_max = tier?.max;
      }

      await completeOnboarding({
        user_role: role,
        persona_answers: persona,
        preferred_district,
        travel_purpose,
        required_facilities,
        preferred_price_min,
        preferred_price_max,
      });
      message.success('感谢您的填写');
      await Promise.resolve(onDone());
      resetLocal();
    } catch (e: unknown) {
      if ((e as { errorFields?: unknown }).errorFields) return;
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || '提交失败');
    } finally {
      setSubmitting(false);
    }
  };

  const nextFromRole = () => {
    if (!role) {
      message.warning('请选择身份');
      return;
    }
    setStep(1);
  };

  const title = step === 0 ? '欢迎使用 · 请选择您的身份' : '完善信息（用于个性化体验）';

  return (
    <Modal
      title={title}
      open={open}
      closable={false}
      maskClosable={false}
      width={560}
      footer={
        <div className="flex justify-between flex-wrap gap-2">
          <Button type="link" onClick={handleSkip} loading={submitting} disabled={!user}>
            跳过调研
          </Button>
          <Space>
            {step === 1 && (
              <Button onClick={() => setStep(0)} disabled={submitting}>
                上一步
              </Button>
            )}
            {step === 0 ? (
              <Button type="primary" onClick={nextFromRole}>
                下一步
              </Button>
            ) : (
              <Button type="primary" onClick={handleFinish} loading={submitting}>
                完成
              </Button>
            )}
          </Space>
        </div>
      }
    >
      <Paragraph type="secondary" className="!mb-4 text-sm">
        约 1 分钟完成，可随时在「个人信息」中修改。我们不会将您的选择用于营销外泄。
      </Paragraph>

      {step === 0 && (
        <Radio.Group
          className="w-full"
          value={role}
          onChange={(e) => setRole(e.target.value)}
        >
          <Space direction="vertical" className="w-full">
            {ROLE_OPTIONS.map((o) => (
              <Radio key={o.value} value={o.value} className="!items-start !leading-relaxed">
                {o.label}
              </Radio>
            ))}
          </Space>
        </Radio.Group>
      )}

      {step === 1 && role && (
        <Form form={form} layout="vertical" requiredMark={false}>
          {role === 'operator' && (
            <>
              <Form.Item
                name="listing_scale"
                label="您目前运营的房源规模？"
                rules={[{ required: true, message: '请选择' }]}
              >
                <Radio.Group options={OPERATOR_LISTING_SCALE} />
              </Form.Item>
              <Form.Item
                name="primary_city"
                label="房源主要所在城市或区域？"
                rules={[{ required: true, message: '请选择' }]}
              >
                <Select options={PRIMARY_CITIES.map((c) => ({ value: c, label: c }))} placeholder="请选择" />
              </Form.Item>
              <Form.Item
                name="operator_focus"
                label="您最想优先使用的功能？（最多 2 项）"
                rules={[
                  { required: true, message: '请至少选一项' },
                  {
                    validator: (_: unknown, v: string[]) =>
                      v && v.length > 2
                        ? Promise.reject(new Error('最多选择 2 项'))
                        : Promise.resolve(),
                  },
                ]}
              >
                <Checkbox.Group options={OPERATOR_FOCUS} />
              </Form.Item>
              <Form.Item
                name="experience_level"
                label="运营经验"
                rules={[{ required: true, message: '请选择' }]}
              >
                <Radio.Group options={EXPERIENCE_LEVEL} />
              </Form.Item>
            </>
          )}

          {role === 'investor' && (
            <>
              <Form.Item name="investment_stage" label="投资阶段？" rules={[{ required: true, message: '请选择' }]}>
                <Radio.Group options={INVESTMENT_STAGE} />
              </Form.Item>
              <Form.Item
                name="budget_tier"
                label="单套预算或总价区间"
                rules={[{ required: true, message: '请选择' }]}
              >
                <Radio.Group options={BUDGET_TIER} />
              </Form.Item>
              <Form.Item
                name="investor_priorities"
                label="最看重的指标？（最多 2 项）"
                rules={[
                  { required: true, message: '请至少选一项' },
                  {
                    validator: (_: unknown, v: string[]) =>
                      v && v.length > 2
                        ? Promise.reject(new Error('最多选择 2 项'))
                        : Promise.resolve(),
                  },
                ]}
              >
                <Checkbox.Group options={INVESTOR_PRIORITIES} />
              </Form.Item>
              <Form.Item name="hold_horizon" label="倾向持有周期？" rules={[{ required: true, message: '请选择' }]}>
                <Radio.Group options={HOLD_HORIZON} />
              </Form.Item>
            </>
          )}

          {role === 'guest' && (
            <>
              <Form.Item
                name="travel_purpose"
                label="浏览参考时，您更关注哪类房源场景？（用于推荐匹配，非预订）"
                rules={[{ required: true, message: '请选择' }]}
              >
                <Radio.Group options={GUEST_TRAVEL_PURPOSE} />
              </Form.Item>
              <Form.Item
                name="guest_price_tier"
                label="常作为参考的价格带（元/晚）？"
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
              <Form.Item
                name="preferred_district"
                label="偏好区域或商圈？"
                rules={[{ required: true, message: '请选择' }]}
              >
                <Select options={DISTRICT_OPTIONS.map((d) => ({ value: d, label: d }))} placeholder="请选择" />
              </Form.Item>
              <Form.Item
                name="required_facilities"
                label="必须有设施？（最多 3 项）"
                rules={[
                  {
                    validator: (_: unknown, v: string[]) =>
                      v && v.length > 3
                        ? Promise.reject(new Error('最多选择 3 项'))
                        : Promise.resolve(),
                  },
                ]}
              >
                <Checkbox.Group options={FACILITY_OPTIONS.map((f) => ({ value: f, label: f }))} />
              </Form.Item>
            </>
          )}

          <Text type="secondary">选填</Text>
          <Form.Item name="acquisition_channel" label="您从哪里知道我们？">
            <Radio.Group options={ACQUISITION_CHANNEL} />
          </Form.Item>
          <Form.Item name="content_interests" label="希望收到的内容？（最多 2 项）">
            <Checkbox.Group options={CONTENT_INTERESTS} />
          </Form.Item>
        </Form>
      )}
    </Modal>
  );
};

export default OnboardingModal;
