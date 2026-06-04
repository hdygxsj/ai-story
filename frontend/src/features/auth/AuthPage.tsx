import { Alert, Button, Card, Form, Input, Space, Typography } from "antd";
import { useState } from "react";

import { login, register } from "../../api/auth";

type AuthPageProps = {
  onAuthenticated: (token: string) => void;
};

type AuthValues = {
  email: string;
  username: string;
  password: string;
};

export function AuthPage({ onAuthenticated }: AuthPageProps) {
  const [form] = Form.useForm<AuthValues>();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleLogin(values: AuthValues) {
    setError(null);
    setLoading(true);
    try {
      const response = await login(values.email, values.password);
      onAuthenticated(response.access_token);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "登录失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleRegister() {
    setError(null);
    setLoading(true);
    try {
      const values = await form.validateFields();
      await register(values.email, values.username, values.password);
      const response = await login(values.email, values.password);
      onAuthenticated(response.access_token);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "注册失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card style={{ maxWidth: 480, width: "100%" }}>
      <Typography.Title level={2}>登录</Typography.Title>
      <Typography.Paragraph type="secondary">
        使用本地账号隔离你的小说、素材和创作记忆。
      </Typography.Paragraph>
      <Form<AuthValues>
        form={form}
        initialValues={{ email: "demo@example.com", username: "demo", password: "secret123" }}
        layout="vertical"
        onFinish={handleLogin}
      >
        <Form.Item name="email" label="邮箱" rules={[{ required: true }, { type: "email" }]}>
          <Input autoComplete="email" />
        </Form.Item>
        <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
          <Input autoComplete="username" />
        </Form.Item>
        <Form.Item name="password" label="密码" rules={[{ required: true, min: 8 }]}>
          <Input.Password autoComplete="current-password" />
        </Form.Item>
        <Space>
          <Button htmlType="submit" loading={loading} type="primary">
            登录
          </Button>
          <Button loading={loading} onClick={handleRegister}>
            注册
          </Button>
        </Space>
      </Form>
      {error ? <Alert message={error} role="alert" showIcon style={{ marginTop: 16 }} type="error" /> : null}
    </Card>
  );
}
