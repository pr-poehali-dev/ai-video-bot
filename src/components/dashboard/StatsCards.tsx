import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import Icon from '@/components/ui/icon';

interface StatsCardsProps {
  stats: {
    total_users: number;
    active_users_24h: number;
    total_orders: number;
    processing_orders: number;
    total_revenue: number;
    credits_spent: number;
    total_errors?: number;
  };
}

export default function StatsCards({ stats }: StatsCardsProps) {
  return (
    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
      <Card className="border-2 border-purple-200 bg-gradient-to-br from-purple-50 to-white">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Всего пользователей</CardTitle>
          <Icon name="Users" className="text-purple-600" size={20} />
        </CardHeader>
        <CardContent>
          <div className="text-3xl font-bold text-purple-700">{stats.total_users}</div>
          <p className="text-xs text-muted-foreground mt-1">
            Активных за 24ч: <span className="font-medium text-purple-600">{stats.active_users_24h}</span>
          </p>
        </CardContent>
      </Card>

      <Card className="border-2 border-pink-200 bg-gradient-to-br from-pink-50 to-white">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Заказы</CardTitle>
          <Icon name="ShoppingCart" className="text-pink-600" size={20} />
        </CardHeader>
        <CardContent>
          <div className="text-3xl font-bold text-pink-700">{stats.total_orders}</div>
          <p className="text-xs text-muted-foreground mt-1">
            В обработке: <span className="font-medium text-pink-600">{stats.processing_orders}</span>
          </p>
        </CardContent>
      </Card>

      <Card className="border-2 border-orange-200 bg-gradient-to-br from-orange-50 to-white">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Доход</CardTitle>
          <Icon name="DollarSign" className="text-orange-600" size={20} />
        </CardHeader>
        <CardContent>
          <div className="text-3xl font-bold text-orange-700">{stats.total_revenue}₽</div>
          <p className="text-xs text-muted-foreground mt-1">
            Потрачено кредитов: <span className="font-medium text-orange-600">{stats.credits_spent}</span>
          </p>
        </CardContent>
      </Card>

      <Card className="border-2 border-red-200 bg-gradient-to-br from-red-50 to-white">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Ошибки</CardTitle>
          <Icon name="AlertTriangle" className="text-red-600" size={20} />
        </CardHeader>
        <CardContent>
          <div className="text-3xl font-bold text-red-700">{stats.total_errors || 0}</div>
          <p className="text-xs text-muted-foreground mt-1">Всего за период</p>
        </CardContent>
      </Card>
    </div>
  );
}
