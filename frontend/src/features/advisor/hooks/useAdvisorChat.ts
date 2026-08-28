import { useMutation } from '@tanstack/react-query';
import { sendAdvisorMessage } from '../services/advisor.service';

export function useAdvisorChat() { return useMutation({ mutationFn: sendAdvisorMessage }); }
