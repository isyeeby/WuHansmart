import React, { useState } from 'react';
import { Form, Input, Button, message, Tabs } from 'antd';
import { UserOutlined, LockOutlined, IdcardOutlined, PhoneOutlined } from '@ant-design/icons';
import { useAuth } from '../context/AuthContext';
import { motion } from 'motion/react';

const { TabPane } = Tabs;

const Login: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('login');
  const { login } = useAuth();
  const [form] = Form.useForm();

  const onLogin = async (values: any) => {
    setLoading(true);
    try {
      await login(values.username, values.password);
      // 登录成功后的跳转和提示已在 AuthContext 中处理
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || error.message || '登录失败';
      message.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const onRegister = async (values: any) => {
    setLoading(true);
    try {
      const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: String(values.username).trim(),
          password: values.password,
          phone: values.phone?.trim?.() || undefined,
          full_name: values.full_name?.trim?.() || undefined,
        }),
      });
      
      // 检查响应是否为空
      const text = await response.text();
      if (!text) {
        throw new Error('后端返回空响应，请检查后端服务是否正常');
      }
      
      let data;
      try {
        data = JSON.parse(text);
      } catch (e) {
        throw new Error(`后端返回非JSON数据: ${text.substring(0, 100)}`);
      }
      
      if (!response.ok) {
        const detail = data.detail;
        let msg: string;
        if (Array.isArray(detail)) {
          msg = detail
            .map((e: { msg?: string }) => e?.msg)
            .filter(Boolean)
            .join('；') || `注册失败 (${response.status})`;
        } else if (typeof detail === 'string') {
          msg = detail;
        } else {
          msg = `注册失败 (${response.status})`;
        }
        throw new Error(msg);
      }

      message.success('注册成功，请登录');
      setActiveTab('login');
      form.resetFields();
    } catch (error: any) {
      message.error(error.message || '注册失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center paper-texture relative overflow-hidden">
      {/* 水墨背景装饰 */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 right-0 w-1/2 h-full opacity-[0.03]">
          <svg viewBox="0 0 400 800" className="w-full h-full">
            <path
              d="M200,0 Q300,200 250,400 Q200,600 300,800"
              fill="none"
              stroke="currentColor"
              strokeWidth="1"
            />
            <path
              d="M100,0 Q50,300 150,500 Q250,700 200,800"
              fill="none"
              stroke="currentColor"
              strokeWidth="0.5"
            />
          </svg>
        </div>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: [0.4, 0, 0.2, 1] }}
        className="login-shell relative z-10 w-full max-w-md px-6 sm:px-8"
      >
        {/* Logo 区域 */}
        <div className="mb-14 text-center sm:mb-16">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.2, duration: 0.6 }}
            className="mb-6 inline-flex h-16 w-16 items-center justify-center rounded-lg border-2 border-[var(--ink-black)] bg-[var(--paper-white)] shadow-[var(--shadow-soft)]"
          >
            <span className="font-serif text-2xl font-bold text-[var(--ink-black)]">宿</span>
          </motion.div>
          <motion.h1
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.6 }}
            className="mb-2 font-serif text-3xl font-semibold tracking-wide text-[var(--ink-black)]"
          >
            武汉民宿智策
          </motion.h1>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5, duration: 0.6 }}
            className="text-xs tracking-wide text-[var(--ink-muted)]"
          >
            民宿价格智能分析与决策
          </motion.p>
        </div>

        {/* 登录表单 */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6, duration: 0.6 }}
          className="login-zen-panel px-8 py-9 sm:px-10 sm:py-10"
        >
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            centered
            className="login-tabs !mb-2"
          >
            <TabPane tab="登录" key="login">
              <Form
                form={form}
                onFinish={onLogin}
                layout="vertical"
                size="large"
              >
                <Form.Item
                  name="username"
                  rules={[{ required: true, message: '请输入用户名' }]}
                  className="mb-5"
                >
                  <Input
                    placeholder="用户名"
                    allowClear
                    prefix={<UserOutlined />}
                    className="login-zen-control"
                    autoComplete="username"
                  />
                </Form.Item>

                <Form.Item
                  name="password"
                  rules={[{ required: true, message: '请输入密码' }]}
                  className="mb-8"
                >
                  <Input.Password
                    placeholder="密码"
                    prefix={<LockOutlined />}
                    className="login-zen-control"
                    autoComplete="current-password"
                  />
                </Form.Item>

                <Form.Item className="mb-0">
                  <Button type="primary" htmlType="submit" loading={loading} block className="login-zen-submit">
                    登录
                  </Button>
                </Form.Item>
              </Form>
            </TabPane>

            <TabPane tab="注册" key="register">
              <Form
                onFinish={onRegister}
                layout="vertical"
                size="large"
              >
                <Form.Item
                  name="username"
                  rules={[
                    { required: true, message: '请输入用户名' },
                    { min: 3, message: '用户名至少 3 个字符' },
                    { max: 50, message: '用户名最多 50 个字符' },
                  ]}
                  validateTrigger={['onBlur', 'onChange']}
                  className="mb-4"
                >
                  <Input
                    placeholder="用户名（3～50 字符）"
                    allowClear
                    prefix={<UserOutlined />}
                    className="login-zen-control"
                    autoComplete="username"
                  />
                </Form.Item>

                <Form.Item
                  name="password"
                  rules={[
                    { required: true, message: '请输入密码' },
                    { min: 6, message: '密码至少 6 位' },
                    { max: 72, message: '密码最长 72 个字符' },
                  ]}
                  validateTrigger={['onBlur', 'onChange']}
                  className="mb-4"
                >
                  <Input.Password
                    placeholder="密码（至少 6 位）"
                    prefix={<LockOutlined />}
                    className="login-zen-control"
                    autoComplete="new-password"
                  />
                </Form.Item>

                <Form.Item name="phone" className="mb-4">
                  <Input
                    placeholder="手机号（可选）"
                    allowClear
                    prefix={<PhoneOutlined />}
                    className="login-zen-control"
                    autoComplete="tel"
                  />
                </Form.Item>

                <Form.Item name="full_name" className="mb-6">
                  <Input
                    placeholder="姓名（可选）"
                    allowClear
                    prefix={<IdcardOutlined />}
                    className="login-zen-control"
                    autoComplete="name"
                  />
                </Form.Item>

                <Form.Item className="mb-0">
                  <Button type="primary" htmlType="submit" loading={loading} block className="login-zen-submit">
                    注册
                  </Button>
                </Form.Item>
              </Form>
            </TabPane>
          </Tabs>
        </motion.div>

        {/* 底部版权 */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.9, duration: 0.6 }}
          className="mt-12 text-center text-xs tracking-wide text-[var(--ink-muted)]"
        >
          © {new Date().getFullYear()} 武汉民宿智策系统
        </motion.p>
      </motion.div>
    </div>
  );
};

export default Login;
