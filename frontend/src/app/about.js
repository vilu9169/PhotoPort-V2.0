
const About = () => {
    return (
        <div>
            <div className=" text-center sm:text-center md:text-left lg:text-left grid space-y-8 grid-cols-1 mt-8  justify-items-center pb-8">
            
                <img src="/ViktorLundin.jpg" alt="Viktor Lundin" className=" relative rounded-full w-40 h-40 align-middle" />
                <div className=" relative align-middle w-1/2">
                    <h1 className=" text-center text-2xl sm:text-2xl md:text-3xl lg:text-3xl">Viktor Lundin</h1>
                    <p className=" text-center text-lg sm:text-lg md:text-xl lg:text-xl">Student, Master in Computer and Information Engineering</p>
                    <p className=" text-center text-lg sm:text-lg md:text-xl lg:text-xl">Uppsala, Sweden</p>
                    <p className=" text-center mt-10">
                        From the sun, 10^45 photons are emitted every second. I steal a couple of them to capture a moment in time.
                    </p>
                </div>
            </div>
        </div>
    );
};

export default About;