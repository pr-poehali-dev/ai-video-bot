import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import Icon from '@/components/ui/icon';

interface DailyRevenueStat {
  date: string;
  revenue: number;
  transaction_count: number;
}

interface DailyRevenueProps {
  stats: DailyRevenueStat[];
}

export default function DailyRevenue({ stats }: DailyRevenueProps) {
  const maxRevenue = Math.max(...stats.map(s => s.revenue), 1);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon name="TrendingUp" size={20} />
          Доход по дням
        </CardTitle>
        <CardDescription>Ежедневная статистика доходов</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {stats.map((stat) => {
            const barHeight = (stat.revenue / maxRevenue) * 100;
            return (
              <div key={stat.date} className="flex items-end gap-3">
                <div className="text-sm text-muted-foreground w-24 text-right">
                  {new Date(stat.date).toLocaleDateString('ru-RU', {
                    day: '2-digit',
                    month: '2-digit'
                  })}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 bg-muted rounded-full h-8 overflow-hidden">
                      <div
                        className="bg-gradient-to-r from-purple-500 via-pink-500 to-orange-500 h-full flex items-center justify-end pr-3 text-white text-sm font-medium transition-all duration-500"
                        style={{ width: `${barHeight}%`, minWidth: '60px' }}
                      >
                        {stat.revenue}₽
                      </div>
                    </div>
                    <div className="text-sm text-muted-foreground w-20">
                      {stat.transaction_count} шт
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
