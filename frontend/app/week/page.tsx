import { Suspense } from "react";

import { Loading } from "@/components/screen-state";
import { WeekScreen } from "@/components/screens/week";

export default function WeekPage() {
  // The week comes from ?start=, which is only known in the browser.
  return (
    <Suspense fallback={<Loading />}>
      <WeekScreen />
    </Suspense>
  );
}
