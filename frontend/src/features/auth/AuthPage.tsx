import { Alert, Button, Card, Form, Input, Space, Tabs, Typography } from "antd";
import { useState } from "react";

import { login, register } from "../../api/auth";

type AuthPageProps = {
  onAuthenticated: (token: string) => void;
};

type LoginValues = {
  login: string;
  password: string;
};

type RegisterValues = {
  email: string;
  username: string;
  password: string;
};

export function AuthPage({ onAuthenticated }: AuthPageProps) {
  const [loginForm] = Form.useForm<LoginValues>();
  const [registerForm] = Form.useForm<RegisterValues>();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleLogin(values: LoginValues) {
    setError(null);
    setLoading(true);
    try {
      const response = await login(values.login, values.password);
      onAuthenticated(response.access_token);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "登录失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleRegister(values: RegisterValues) {
    setError(null);
    setLoading(true);
    try {
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
      <Typography.Title level={2}>欢迎使用 AI Story</Typography.Title>
      <Typography.Paragraph type="secondary">
        使用本地账号隔离你的小说、素材和创作记忆。首次使用请先注册账号。
      </Typography.Paragraph>
      <Tabs
        items={[
          {
            key: "login",
            label: "登录",
            children: (
              <Form<LoginValues> form={loginForm} layout="vertical" onFinish={handleLogin}>
                <Form.Item name="login" label="邮箱或用户名" rules={[{ required: true, min: 3 }]}>
                  <Input autoComplete="username" placeholder="输入注册时的邮箱或用户名" />
                </Form.Item>
                <Form.Item name="password" label="密码" rules={[{ required: true, min: 8 }]}>
                  <Input.Password autoComplete="current-password" />
                </Form.Item>
                <Button htmlType="submit" loading={loading} type="primary">
                  登录
                </Button>
              </Form>
            ),
          },
          {
            key: "register",
            label: "注册",
            children: (
              <Form<RegisterValues> form={registerForm} layout="vertical" onFinish={handleRegister}>
                <Form.Item name="email" label="邮箱" rules={[{ required: true }, { type: "email" }]}>
                  <Input autoComplete="email" />
                </Form.Item>
                <Form.Item name="username" label="用户名" rules={[{ required: true, min: 3 }]}>
                  <Input autoComplete="username" />
                </Form.Item>
                <Form.Item name="password" label="密码" rules={[{ required: true, min: 8 }]}>
                  <Input.Password autoComplete="new-password" />
                </Form.Item>
                <Button htmlType="submit" loading={loading} type="primary">
                  注册并登录
                </Button>
              </Form>
            ),
          },
        ]}
      />
      {error ? <Alert message={error} role="alert" showIcon style={{ marginTop: 16 }} type="error" /> : null}
    </Card>
  );
}
