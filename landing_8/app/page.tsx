import Nav from "@/components/Nav";
import Hero from "@/components/Hero";
import HowItWorks from "@/components/HowItWorks";
import Plane from "@/components/Plane";
import Proof from "@/components/Proof";
import Versus from "@/components/Versus";
import Start from "@/components/Start";
import Footer from "@/components/Footer";

export default function Home() {
  return (
    <>
      <Nav />
      <main>
        <Hero />
        <HowItWorks />
        <Plane />
        <Proof />
        <Versus />
        <Start />
      </main>
      <Footer />
    </>
  );
}
