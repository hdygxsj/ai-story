import { Alert, Button, Card, Form, Input, Typography } from "antd";
import { useState } from "react";

import { login } from "../../api/auth";

type LoginPageProps = {
  onAuthenticated: (token: string) => void;
  onNavigateRegister: () => void;
  successMessage?: string | null;
};

type LoginValues = {
  login: string;
  password: string;
};

export function LoginPage({ onAuthenticated, onNavigateRegister, successMessage = null }: LoginPageProps) {
  const [form] = Form.useForm<LoginValues>();
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

  return (
    <Card style={{ maxWidth: 480, width: "100%" }}>
      <Typography.Title level={2}>登录</Typography.Title>
      <Typography.Paragraph type="secondary">
        使用本地账号隔离你的小说、素材和创作记忆。
      </Typography.Paragraph>
      <Form<LoginValues> form={form} layout="vertical" onFinish={handleLogin}>
        <Form.Item name="login" label="邮箱或用户名" rules={[{ required: true, min: 3 }]}>
          <Input autoComplete="username" placeholder="输入注册时的邮箱或用户名" />
        </Form.Item>
        <Form.Item name="password" label="密码" rules={[{ required: true, min: 8 }]}>
          <Input.Password autoComplete="current-password" />
        </Form.Item>
        <Button block htmlType="submit" loading={loading} type="primary">
          登录
        </Button>
      </Form>
      <Typography.Paragraph style={{ marginBottom: 0, marginTop: 16, textAlign: "center" }}>
        还没有账号？{" "}
        <Typography.Link onClick={onNavigateRegister}>去注册</Typography.Link>
      </Typography.Paragraph>
      {successMessage ? (
        <Alert message={successMessage} role="status" showIcon style={{ marginTop: 16 }} type="success" />
      ) : null}
      {error ? <Alert message={error} role="alert" showIcon style={{ marginTop: 16 }} type="error" /> : null}
    </Card>
  );
}
