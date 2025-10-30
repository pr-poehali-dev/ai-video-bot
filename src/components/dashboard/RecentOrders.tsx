import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import Icon from '@/components/ui/icon';

interface Order {
  order_id: number;
  user_id: number;
  order_type: string;
  status: string;
  cost: number;
  created_at: string;
  username: string;
  first_name: string;
}

interface RecentOrdersProps {
  orders: Order[];
}

export default function RecentOrders({ orders }: RecentOrdersProps) {
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

  const getStatusBadge = (status: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
      pending: 'outline',
      processing: 'secondary',
      completed: 'default',
      failed: 'destructive',
      cancelled: 'outline'
    };
    
    const labels: Record<string, string> = {
      pending: 'Ожидает',
      processing: 'Обработка',
      completed: 'Готово',
      failed: 'Ошибка',
      cancelled: 'Отменён'
    };

    return <Badge variant={variants[status] || 'outline'}>{labels[status] || status}</Badge>;
  };

  const getOrderTypeIcon = (type: string) => {
    const icons: Record<string, string> = {
      preview: 'Image',
      'text-to-video': 'Video',
      'image-to-video': 'Film',
      storyboard: 'Clapperboard'
    };
    return icons[type] || 'FileVideo';
  };

  const getOrderTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      preview: 'Превью',
      'text-to-video': 'Текст → Видео',
      'image-to-video': 'Изображение → Видео',
      storyboard: 'Storyboard'
    };
    return labels[type] || type;
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon name="ShoppingCart" size={20} />
          Последние заказы
        </CardTitle>
        <CardDescription>Недавние заказы пользователей</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b">
                <th className="text-left p-2 font-medium">ID</th>
                <th className="text-left p-2 font-medium">Пользователь</th>
                <th className="text-left p-2 font-medium">Тип</th>
                <th className="text-left p-2 font-medium">Статус</th>
                <th className="text-left p-2 font-medium">Стоимость</th>
                <th className="text-left p-2 font-medium">Дата</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr key={order.order_id} className="border-b hover:bg-muted/50">
                  <td className="p-2 font-mono text-sm">{order.order_id}</td>
                  <td className="p-2">
                    <div>
                      <div className="font-medium">{order.first_name}</div>
                      <div className="text-sm text-muted-foreground">
                        {order.username ? `@${order.username}` : `ID: ${order.user_id}`}
                      </div>
                    </div>
                  </td>
                  <td className="p-2">
                    <div className="flex items-center gap-2">
                      <Icon name={getOrderTypeIcon(order.order_type)} size={16} />
                      <span className="text-sm">{getOrderTypeLabel(order.order_type)}</span>
                    </div>
                  </td>
                  <td className="p-2">{getStatusBadge(order.status)}</td>
                  <td className="p-2">
                    <Badge variant="outline">{order.cost}₽</Badge>
                  </td>
                  <td className="p-2 text-sm text-muted-foreground">
                    {formatDate(order.created_at)}
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
