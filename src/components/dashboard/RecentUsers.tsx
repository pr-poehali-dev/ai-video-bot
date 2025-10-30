import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import Icon from '@/components/ui/icon';

interface User {
  user_id: number;
  username: string;
  first_name: string;
  balance: number;
  created_at: string;
  last_activity: string;
  is_blocked: boolean;
}

interface RecentUsersProps {
  users: User[];
  onUpdateBalance: (userId: number) => void;
}

export default function RecentUsers({ users, onUpdateBalance }: RecentUsersProps) {
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon name="Users" size={20} />
          Последние пользователи
        </CardTitle>
        <CardDescription>Недавно зарегистрированные пользователи</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b">
                <th className="text-left p-2 font-medium">ID</th>
                <th className="text-left p-2 font-medium">Пользователь</th>
                <th className="text-left p-2 font-medium">Баланс</th>
                <th className="text-left p-2 font-medium">Регистрация</th>
                <th className="text-left p-2 font-medium">Активность</th>
                <th className="text-left p-2 font-medium">Статус</th>
                <th className="text-left p-2 font-medium">Действия</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.user_id} className="border-b hover:bg-muted/50">
                  <td className="p-2 font-mono text-sm">{user.user_id}</td>
                  <td className="p-2">
                    <div>
                      <div className="font-medium">{user.first_name}</div>
                      <div className="text-sm text-muted-foreground">
                        {user.username ? `@${user.username}` : 'Нет username'}
                      </div>
                    </div>
                  </td>
                  <td className="p-2">
                    <Badge variant={user.balance > 0 ? 'default' : 'outline'}>
                      {user.balance}₽
                    </Badge>
                  </td>
                  <td className="p-2 text-sm text-muted-foreground">
                    {formatDate(user.created_at)}
                  </td>
                  <td className="p-2 text-sm text-muted-foreground">
                    {formatDate(user.last_activity)}
                  </td>
                  <td className="p-2">
                    {user.is_blocked ? (
                      <Badge variant="destructive">Заблокирован</Badge>
                    ) : (
                      <Badge variant="default" className="bg-green-500">Активен</Badge>
                    )}
                  </td>
                  <td className="p-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => onUpdateBalance(user.user_id)}
                    >
                      <Icon name="Wallet" size={14} className="mr-1" />
                      Баланс
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
