import { Alert, Button, Card, Form, Input, Typography } from "antd";
import { useState } from "react";

import { register } from "../../api/auth";

type RegisterPageProps = {
  onNavigateLogin: () => void;
  onRegistered: () => void;
};

type RegisterValues = {
  email: string;
  username: string;
  password: string;
};

export function RegisterPage({ onNavigateLogin, onRegistered }: RegisterPageProps) {
  const [form] = Form.useForm<RegisterValues>();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleRegister(values: RegisterValues) {
    setError(null);
    setLoading(true);
    try {
      await register(values.email, values.username, values.password);
      form.resetFields();
      onRegistered();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "注册失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card style={{ maxWidth: 480, width: "100%" }}>
      <Typography.Title level={2}>注册</Typography.Title>
      <Typography.Paragraph type="secondary">
        创建本地账号，开始管理你的小说、素材和创作记忆。
      </Typography.Paragraph>
      <Form<RegisterValues> form={form} layout="vertical" onFinish={handleRegister}>
        <Form.Item name="email" label="邮箱" rules={[{ required: true }, { type: "email" }]}>
          <Input autoComplete="email" />
        </Form.Item>
        <Form.Item name="username" label="用户名" rules={[{ required: true, min: 3 }]}>
          <Input autoComplete="username" />
        </Form.Item>
        <Form.Item name="password" label="密码" rules={[{ required: true, min: 8 }]}>
          <Input.Password autoComplete="new-password" />
        </Form.Item>
        <Button block htmlType="submit" loading={loading} type="primary">
          注册
        </Button>
      </Form>
      <Typography.Paragraph style={{ marginBottom: 0, marginTop: 16, textAlign: "center" }}>
        已有账号？{" "}
        <Typography.Link onClick={onNavigateLogin}>去登录</Typography.Link>
      </Typography.Paragraph>
      {error ? <Alert message={error} role="alert" showIcon style={{ marginTop: 16 }} type="error" /> : null}
    </Card>
  );
}
