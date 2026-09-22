export const SAMPLE_PROMPTS = [
  { text: "What accounts does customer alice have?", risky: false },
  { text: "What's the balance on account acc-1001?", risky: false },
  { text: "What's the status of the loan application for customer ravi?", risky: false },
  { text: "Please open a new savings account for customer ravi.", risky: true },
  { text: "Transfer $100 from acc-1001 to acc-2001.", risky: true },
];
