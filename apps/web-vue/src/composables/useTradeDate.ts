import { ref } from 'vue';
import { getShanghaiTradeDate } from '@/utils/domain/marketOverview';

export function useTradeDate(initialDate?: string) {
  const tradeDate = ref(initialDate || getShanghaiTradeDate());

  function setTradeDate(value: string) {
    const next = value.trim();
    if (next) tradeDate.value = next;
  }

  return { tradeDate, setTradeDate };
}
